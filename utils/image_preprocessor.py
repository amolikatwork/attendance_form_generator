import logging
from pathlib import Path
from PIL import Image
import numpy as np

logger = logging.getLogger(__name__)


def preprocess_image(image_path, output_path=None):
    """
    Preprocess image for better OCR results.
    
    Args:
        image_path: Path to input image
        output_path: Path to save preprocessed image (optional)
    
    Returns:
        PIL.Image: Preprocessed image
    """
    try:
        # Open image
        img = Image.open(image_path)
        
        # Convert to RGB if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Convert to numpy array for processing
        img_array = np.array(img)
        
        # Convert to grayscale for better contrast
        if len(img_array.shape) == 3:
            # Weighted grayscale conversion
            img_gray = np.dot(img_array[...,:3], [0.299, 0.587, 0.114])
        else:
            img_gray = img_array
        
        # Apply contrast enhancement
        # Normalize to 0-255
        img_gray = ((img_gray - img_gray.min()) / (img_gray.max() - img_gray.min()) * 255).astype(np.uint8)
        
        # Apply thresholding for better OCR
        threshold = 150
        img_binary = np.where(img_gray > threshold, 255, 0).astype(np.uint8)
        
        # Convert back to PIL Image
        result = Image.fromarray(img_binary)
        
        # Save preprocessed image if output path provided
        if output_path:
            result.save(output_path)
            logger.info(f"Preprocessed image saved to {output_path}")
        
        logger.info(f"Image preprocessing complete for {image_path}")
        return result
    
    except Exception as e:
        logger.error(f"Error preprocessing image: {str(e)}")
        # Return original image on error
        return Image.open(image_path)


def denoise_image(image_path):
    """
    Apply denoising to improve OCR accuracy.
    
    Args:
        image_path: Path to input image
    
    Returns:
        PIL.Image: Denoised image
    """
    try:
        img = Image.open(image_path)
        
        # Apply median filter for noise reduction
        from PIL import ImageFilter
        denoised = img.filter(ImageFilter.MedianFilter(size=3))
        
        logger.info(f"Denoising applied to {image_path}")
        return denoised
    
    except Exception as e:
        logger.error(f"Error denoising image: {str(e)}")
        return Image.open(image_path)


def upscale_image(image_path, scale_factor=2):
    """
    Upscale image for better OCR on small text.
    
    Args:
        image_path: Path to input image
        scale_factor: Scaling factor (default 2x)
    
    Returns:
        PIL.Image: Upscaled image
    """
    try:
        img = Image.open(image_path)
        
        # Calculate new size
        new_width = img.width * scale_factor
        new_height = img.height * scale_factor
        
        # Upscale using high-quality resampling
        upscaled = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        logger.info(f"Image upscaled from {img.size} to {upscaled.size}")
        return upscaled
    
    except Exception as e:
        logger.error(f"Error upscaling image: {str(e)}")
        return Image.open(image_path)
