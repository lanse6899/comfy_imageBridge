import os
from PIL import ImageOps
import logging
import folder_paths
import torch
import nodes
from PIL import Image
import numpy as np
from impact import utils

# NOTE: this should not be `from . import core`.
# I don't know why but... 'from .' and 'from impact' refer to different core modules.
# This separates global variables of the core module and breaks the preview bridge.
from impact import core
# <--
import random
import time


# Initialize class-level cache variables
image_bridge_x_image_id_map = {}
image_bridge_x_name_map = {}
image_bridge_x_cache = {}
image_bridge_x_last_mask_cache = {}
ibx_id_cnt = time.time()


class ImageBridgeX:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {
                    "images": ("IMAGE",),
                    "image": ("STRING", {"default": ""}),
                    },
                "optional": {
                    "block": ("BOOLEAN", {"default": False, "label_on": "if_empty_mask", "label_off": "never", "tooltip": "is_empty_mask: If the mask is empty, the execution is stopped.\nnever: The execution is never stopped."}),
                    "restore_mask": (["never", "always", "if_same_size"], {"tooltip": "if_same_size: If the changed input image is the same size as the previous image, restore using the last saved mask\nalways: Whenever the input image changes, always restore using the last saved mask\nnever: Do not restore the mask.\n`restore_mask` has higher priority than `block`"}),
                    },
                "hidden": {"unique_id": "UNIQUE_ID", "extra_pnginfo": "EXTRA_PNGINFO"},
                }

    RETURN_TYPES = ("IMAGE", "MASK", )

    FUNCTION = "doit"

    OUTPUT_NODE = True

    CATEGORY = "ImpactPack/Util"

    DESCRIPTION = "This is a feature that allows you to edit and send a Mask over a image.\nIf the block is set to 'is_empty_mask', the execution is stopped when the mask is empty."

    def __init__(self):
        super().__init__()
        self.output_dir = folder_paths.get_temp_directory()
        self.type = "temp"
        self.prev_hash = None

    @staticmethod
    def load_image(pb_id):
        is_fail = False
        if pb_id not in image_bridge_x_image_id_map:
            is_fail = True

        if not is_fail:
            image_path, ui_item = image_bridge_x_image_id_map[pb_id]
            if not os.path.isfile(image_path):
                is_fail = True

        if not is_fail:
            i = Image.open(image_path)
            i = ImageOps.exif_transpose(i)
            image = i.convert("RGB")
            image = np.array(image).astype(np.float32) / 255.0
            image = torch.from_numpy(image)[None,]

            if 'A' in i.getbands():
                mask = np.array(i.getchannel('A')).astype(np.float32) / 255.0
                mask = 1. - torch.from_numpy(mask)
            else:
                mask = torch.zeros((64, 64), dtype=torch.float32, device="cpu")
        else:
            image = utils.empty_pil_tensor()
            mask = torch.zeros((64, 64), dtype=torch.float32, device="cpu")
            ui_item = {
                "filename": 'empty.png',
                "subfolder": '',
                "type": 'temp'
            }

        return image, mask.unsqueeze(0), ui_item

    @staticmethod
    def register_clipspace_image(clipspace_path, node_id):
        """Register a clipspace image file in the image bridge x system.
        
        This handles the case where ComfyUI's mask editor creates clipspace files
        that need to be integrated with the image bridge x system.
        """
        # Remove [input] suffix if present
        clean_path = clipspace_path.replace(" [input]", "").replace("[input]", "")
        
        # Try to find the actual clipspace file
        input_dir = folder_paths.get_input_directory()
        potential_paths = [
            clean_path,
            os.path.join(input_dir, clean_path),
            os.path.join(input_dir, "clipspace", os.path.basename(clean_path)),
            os.path.abspath(clean_path),
        ]
        
        actual_file = None
        for path in potential_paths:
            if os.path.isfile(path):
                actual_file = path
                break
        
        if not actual_file:
            return False
            
        # Create ui_item for the clipspace file
        ui_item = {
            'filename': os.path.basename(actual_file),
            'subfolder': 'clipspace',
            'type': 'input'
        }
        
        # Register it using the image bridge x system
        ImageBridgeX.set_image_bridge_x_image(node_id, actual_file, ui_item)
        # Also register under the original clipspace path for compatibility
        image_bridge_x_image_id_map[clipspace_path] = (actual_file, ui_item)
        
        return True

    @staticmethod
    def set_image_bridge_x_image(node_id, file, item):
        """Set image in the image bridge x system."""
        global ibx_id_cnt
        
        if (node_id, file) in image_bridge_x_name_map:
            pb_id, _ = image_bridge_x_name_map[node_id, file]
            if pb_id.startswith(f"${node_id}"):
                return pb_id

        pb_id = f"${node_id}-{ibx_id_cnt}"
        image_bridge_x_image_id_map[pb_id] = (file, item)
        image_bridge_x_name_map[node_id, file] = (pb_id, item)
        if os.path.isfile(file):
            i = Image.open(file)
            i = ImageOps.exif_transpose(i)
            if 'A' in i.getbands():
                mask = np.array(i.getchannel('A')).astype(np.float32) / 255.0
                mask = 1. - torch.from_numpy(mask)
                image_bridge_x_last_mask_cache[node_id] = mask.unsqueeze(0)
        ibx_id_cnt += 1

        return pb_id

    def doit(self, images, image, unique_id, block=False, restore_mask="never", prompt=None, extra_pnginfo=None):
        need_refresh = False
        images_changed = False

        # Check if images have changed (this determines if we start fresh)
        if unique_id not in image_bridge_x_cache:
            need_refresh = True
            images_changed = True
        elif image_bridge_x_cache[unique_id][0] is not images:
            need_refresh = True
            images_changed = True

        # If images changed, clear the old cache entries to ensure fresh start
        if images_changed:
            # Collect all old paths associated with this unique_id
            old_paths = set()
            old_pb_ids = set()
            old_image_strings = set()
            
            # Find all paths in name_map for this unique_id
            keys_to_remove = []
            for key in list(image_bridge_x_name_map.keys()):
                if isinstance(key, tuple) and len(key) == 2 and key[0] == unique_id:
                    old_path = key[1]
                    old_paths.add(old_path)
                    # Get the pb_id associated with this path
                    pb_id, item = image_bridge_x_name_map[key]
                    if pb_id:
                        old_pb_ids.add(pb_id)
                    keys_to_remove.append(key)
            
            # Remove keys from name_map
            for key in keys_to_remove:
                del image_bridge_x_name_map[key]
            
            # Remove old pb_ids from image_id_map
            for pb_id in old_pb_ids:
                if pb_id in image_bridge_x_image_id_map:
                    del image_bridge_x_image_id_map[pb_id]
            
            # Remove all entries in image_id_map that point to old paths
            # This includes both pb_ids and image strings
            entries_to_remove = []
            for key, (path, item) in list(image_bridge_x_image_id_map.items()):
                if path in old_paths:
                    entries_to_remove.append(key)
                    # Track if current image string is being removed
                    if key == image:
                        old_image_strings.add(key)
            
            # Remove all entries pointing to old paths
            for key in entries_to_remove:
                del image_bridge_x_image_id_map[key]
            
            # If the current image string was removed (pointed to old path), force refresh
            if image:
                if image in old_image_strings:
                    # Current image string was removed because it pointed to old path
                    need_refresh = True
                elif image not in image_bridge_x_image_id_map:
                    # Image string is not in cache after cleanup, force refresh to use new image
                    need_refresh = True
            
            # Clear mask cache unless restore_mask is set to "always" or "if_same_size"
            if restore_mask not in ["always", "if_same_size"] and unique_id in image_bridge_x_last_mask_cache:
                del image_bridge_x_last_mask_cache[unique_id]

        # Handle clipspace files that aren't registered in the image bridge x system
        # This only applies when images haven't changed (same image, new mask scenario)
        # If images changed, we should always refresh to avoid using old cached image strings
        if not need_refresh and image not in image_bridge_x_image_id_map:
            # Check if this is a clipspace file that needs to be registered
            is_clipspace = image and ("clipspace" in image.lower() or "[input]" in image)
            if is_clipspace:
                if not ImageBridgeX.register_clipspace_image(image, unique_id):
                    need_refresh = True
            else:
                need_refresh = True

        if not need_refresh:
            pixels, mask, path_item = ImageBridgeX.load_image(image)
            image = [path_item]
        else:
            # When refreshing (new image), clear the old image string mapping
            # This ensures that if the UI still shows the old string, it won't be valid
            if image and image in image_bridge_x_image_id_map:
                # Check if this image string points to an old path
                old_path, old_item = image_bridge_x_image_id_map[image]
                # If images changed, this is definitely an old mapping, remove it
                if images_changed:
                    del image_bridge_x_image_id_map[image]
            # For new images (images_changed=True), we want to start fresh regardless of restore_mask
            # For same image with refresh needed, respect the restore_mask setting
            # Exception: when restore_mask is "always", restore even with new images
            # Exception: when restore_mask is "if_same_size", allow restoration to check size compatibility
            if restore_mask != "never" and (not images_changed or restore_mask in ["always", "if_same_size"]):
                mask = image_bridge_x_last_mask_cache.get(unique_id)
                if mask is None:
                    mask = None
                elif restore_mask == "if_same_size" and mask.shape[1:] != images.shape[1:3]:
                    # For if_same_size, clear mask if dimensions don't match
                    mask = None
                # For "always", keep the mask regardless of size
            else:
                mask = None

            if mask is None:
                mask = torch.zeros((64, 64), dtype=torch.float32, device="cpu")
                res = nodes.PreviewImage().save_images(images, filename_prefix="ImageBridgeX/IBX-", prompt=prompt, extra_pnginfo=extra_pnginfo)
            else:
                masked_images = utils.tensor_convert_rgba(images)
                resized_mask = utils.resize_mask(mask, (images.shape[1], images.shape[2])).unsqueeze(3)
                resized_mask = 1 - resized_mask
                utils.tensor_putalpha(masked_images, resized_mask)
                res = nodes.PreviewImage().save_images(masked_images, filename_prefix="ImageBridgeX/IBX-", prompt=prompt, extra_pnginfo=extra_pnginfo)

            image2 = res['ui']['images']
            pixels = images

            path = os.path.join(folder_paths.get_temp_directory(), 'ImageBridgeX', image2[0]['filename'])
            # Generate new pb_id for the new image
            new_pb_id = ImageBridgeX.set_image_bridge_x_image(unique_id, path, image2[0])
            
            # Store the new mapping using the new pb_id
            image_bridge_x_image_id_map[new_pb_id] = (path, image2[0])
            image_bridge_x_name_map[unique_id, path] = (new_pb_id, image2[0])
            image_bridge_x_cache[unique_id] = (images, image2)
            
            # When images changed, don't map old image string to new path
            # This ensures old string becomes invalid and won't be used
            # Only map if it's a new, valid image string (not from old cache)
            if image and image != new_pb_id:
                # Check if this image string was in the old cache (should have been removed)
                if image not in image_bridge_x_image_id_map:
                    # This is a new image string (not from old cache), map it to new path
                    image_bridge_x_image_id_map[image] = (path, image2[0])
                # If image string is still in cache, it means it wasn't removed (pointed to new path)
                # In that case, we keep the existing mapping

            image = image2

        is_empty_mask = torch.all(mask == 0)

        if block and is_empty_mask and core.is_execution_model_version_supported():
            from comfy_execution.graph import ExecutionBlocker
            result = ExecutionBlocker(None), ExecutionBlocker(None)
        elif block and is_empty_mask:
            logging.warning("[Impact Pack] ImageBridgeX: ComfyUI is outdated - blocking feature is disabled.")
            result = pixels, mask
        else:
            result = pixels, mask

        if not is_empty_mask:
            image_bridge_x_last_mask_cache[unique_id] = mask

        # Prepare UI return data
        ui_data = {"images": image}
        
        # widgets_values order matches INPUT_TYPES: [images, image, block, restore_mask]
        # Required fields: images (index 0), image (index 1)
        # Optional fields: block (index 2), restore_mask (index 3)
        # When images changed, clear the image string field in UI
        if images_changed:
            # Return widgets_values to update the image field to empty string
            # images (index 0) is IMAGE type, set to None (cannot be updated via widgets_values)
            # image (index 1) is STRING type, set to "" to clear it
            # block (index 2) and restore_mask (index 3) set to None to keep original values
            ui_data["widgets_values"] = [None, "", None, None]

        return {
            "ui": ui_data,
            "result": result,
        }

