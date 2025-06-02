import requests
import logging
from werkzeug.datastructures import FileStorage

class ImageService:
    def __init__(self, api_key):
        self.api_key = api_key
        self.upload_url = "https://api.imgbb.com/1/upload"

    def upload_image(self, file: FileStorage):
        """
        Upload an image to ImgBB.
        Args:
            file: FileStorage object containing the image file.
        Returns:
            dict: {'success': bool, 'url': str or None, 'error': str or None}
        """
        try:
            # Prepare the file for upload
            files = {'image': (file.filename, file.stream, file.mimetype)}
            params = {'key': self.api_key}

            # Send POST request to ImgBB
            response = requests.post(self.upload_url, files=files, data=params)

            # Check response
            if response.status_code == 200 and response.json().get('status') == 200:
                image_url = response.json()['data']['url']
                return {'success': True, 'url': image_url, 'error': None}
            else:
                error_msg = response.json().get('error', {}).get('message', 'Unknown error')
                logging.error(f"ImgBB API error: {error_msg}, status: {response.status_code}")
                return {'success': False, 'url': None, 'error': error_msg}
        except Exception as e:
            logging.error(f"Image upload failed: {str(e)}")
            return {'success': False, 'url': None, 'error': f"An error occurred: {str(e)}"}