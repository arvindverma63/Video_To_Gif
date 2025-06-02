from flask import Flask, request, jsonify
from flasgger import Swagger, swag_from
from moviepy.editor import VideoFileClip
import os
import tempfile
import logging
from services.image_service import ImageService
from dotenv import load_dotenv

# Initialize Flask app
app = Flask(__name__)

# Load environment variables
load_dotenv()
IMGBB_API_KEY = os.getenv('IMGBB_API_KEY')

# Initialize ImageService
image_service = ImageService(IMGBB_API_KEY)

# Configure logging
logging.basicConfig(level=logging.ERROR)

# Configure Swagger
app.config['SWAGGER'] = {
    'title': 'Video to GIF Converter API',
    'uiversion': 3,
    'version': '1.0.0',
    'description': 'API for converting videos to GIFs and uploading to ImgBB'
}
swagger = Swagger(app)

@app.route('/convert-video-to-gif', methods=['POST'])
@swag_from('swagger.yml')
def convert_video_to_gif():
    """
    Convert a video to a GIF and upload to ImgBB.
    """
    # Validate request
    if 'video' not in request.files:
        return jsonify({'success': False, 'error': 'No video file provided'}), 400

    video_file = request.files['video']
    allowed_extensions = {'mp4', 'webm', 'mov', 'avi'}
    max_size_mb = 20

    # Validate file extension
    if not video_file.filename.lower().endswith(tuple(allowed_extensions)):
        return jsonify({
            'success': False,
            'error': 'Invalid file format. Supported formats: mp4, webm, mov, avi'
        }), 400

    # Validate file size
    video_file.seek(0, os.SEEK_END)
    file_size = video_file.tell()
    if file_size > max_size_mb * 1024 * 1024:
        return jsonify({
            'success': False,
            'error': f'File size exceeds {max_size_mb}MB limit'
        }), 400
    video_file.seek(0)

    temp_gif_path = None
    try:
        # Create temporary files for video and GIF
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
            video_file.save(temp_video.name)
            temp_video_path = temp_video.name

        temp_gif_path = tempfile.mktemp(suffix='.gif')

        # Convert video to GIF using moviepy
        clip = VideoFileClip(temp_video_path)
        clip_resized = clip.resize((320, 240))  # Resize to 320x240
        clip_resized.write_duration(5).write_gif(temp_gif_path, fps=10)

        # Close the clip to release resources
        clip.close()
        clip_resized.close()

        # Upload GIF to ImgBB
        with open(temp_gif_path, 'rb') as gif_file:
            gif_file_storage = FileStorage(
                stream=gif_file,
                filename=os.path.basename(temp_gif_path),
                content_type='image/gif'
            )
            result = image_service.upload_image(gif_file_storage)

        # Clean up temporary files
        os.unlink(temp_video_path)
        os.unlink(temp_gif_path)

        if not result['success']:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400

        return jsonify({
            'success': True,
            'gif_url': result['url']
        }), 200

    except Exception as e:
        # Clean up temporary files in case of error
        if temp_gif_path and os.path.exists(temp_gif_path):
            os.unlink(temp_gif_path)
        if os.path.exists(temp_video_path):
            os.unlink(temp_video_path)

        logging.error(f"Video to GIF conversion failed: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Failed to convert video to GIF: {str(e)}'
        }), 500

if __name__ == '__main__':
    app.run(debug=True)