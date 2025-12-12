"""
ImageBridgeX - A bridge node for image editing with mask support
Based on PreviewBridge from Impact Pack
"""

import folder_paths
import os
import sys
import logging

# Add the parent directory to the path to import impact modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

try:
    from .image_bridge_x import ImageBridgeX
except ImportError as e:
    logging.error(f"[ImageBridgeX] Failed to import ImageBridgeX: {e}")
    raise

NODE_CLASS_MAPPINGS = {
    "ImageBridgeX": ImageBridgeX,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ImageBridgeX": "🔵BB桥接预览",
}

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']

