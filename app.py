from flask import Flask, request, jsonify
from flask_swagger_ui import get_swaggerui_blueprint
from moviepy.editor import VideoFileClip
import os
import uuid
import requests
import base64

app = Flask(__name__)

# Swagger UI setup
SWAGGER_URL = '/swagger'
API_URL = '/static/swagger.json'
swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={'app_name': "Video to GIF Converter"}
)
app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

# Directory to store uploaded videos and generated GIFs temporarily
UPLOAD_FOLDER = 'uploads'
GIF_FOLDER = 'gifs'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(GIF_FOLDER, exist_ok=True)

# ImgBB API key
IMGBB_API_KEY = "340c70b25e651e2ff88ea1bfa25556c8"

# Maximum GIF size (30 MB in bytes)
MAX_GIF_SIZE = 30 * 1024 * 1024

@app.route('/convert-to-gif', methods=['POST'])
def convert_to_gif():
    """
    Convert uploaded video to GIF and upload to ImgBB, ensuring GIF is under 30 MB
    ---
    tags:
      - Video Conversion
    consumes:
      - multipart/form-data
    parameters:
      - in: formData
        name: video
        type: file
        required: true
        description: Video file to convert to GIF
    responses:
      200:
        description: Successfully converted video to GIF and uploaded to ImgBB
        schema:
          type: object
          properties:
            success: 
              type: boolean
            gif_url:
              type: string
      400:
        description: No video file provided or invalid file
      500:
        description: Error during conversion or upload
    """
    if 'video' not in request.files:
        return jsonify({'success': False, 'error': 'No video file provided'}), 400
    
    video_file = request.files['video']
    
    # Validate file extension
    if not video_file.filename.lower().endswith(('.mp4', '.avi', '.mov')):
        return jsonify({'success': False, 'error': 'Invalid video format'}), 400

    # Generate unique filename
    unique_id = str(uuid.uuid4())
    video_path = os.path.join(UPLOAD_FOLDER, f"{unique_id}_{video_file.filename}")
    gif_filename = f"{unique_id}.gif"
    gif_path = os.path.join(GIF_FOLDER, gif_filename)

    try:
        # Save uploaded video temporarily
        video_file.save(video_path)

        # Convert video to GIF
        video_clip = VideoFileClip(video_path)
        
        # Initial GIF conversion with default settings
        video_clip.write_gif(gif_path, fps=10)  # Start with reasonable FPS
        
        # Check GIF size
        gif_size = os.path.getsize(gif_path)
        compression_attempts = 0
        max_attempts = 3
        
        while gif_size > MAX_GIF_SIZE and compression_attempts < max_attempts:
            compression_attempts += 1
            # Reduce quality: lower FPS, resolution, or duration
            fps = max(5, 10 - compression_attempts * 2)  # Reduce FPS (min 5)
            scale_factor = 1.0 - (compression_attempts * 0.2)  # Reduce resolution by 20% each attempt
            new_width = int(video_clip.w * scale_factor)
            new_height = int(video_clip.h * scale_factor)
            
            # Ensure even dimensions (required by some codecs)
            new_width = new_width if new_width % 2 == 0 else new_width - 1
            new_height = new_height if new_height % 2 == 0 else new_height - 1
            
            # Reconvert with compressed settings
            video_clip_resized = video_clip.resize((new_width, new_height))
            video_clip_resized.write_gif(gif_path, fps=fps, program='ffmpeg')
            gif_size = os.path.getsize(gif_path)
        
        video_clip.close()

        if gif_size > MAX_GIF_SIZE:
            raise Exception("Unable to compress GIF below 30 MB after multiple attempts")

        # Delete the uploaded video file
        if os.path.exists(video_path):
            os.remove(video_path)

        # Upload GIF to ImgBB
        with open(gif_path, 'rb') as gif_file:
            encoded_gif = base64.b64encode(gif_file.read()).decode('utf-8')
        
        imgbb_response = requests.post(
            "https://api.imgbb.com/1/upload",
            data={
                "key": IMGBB_API_KEY,
                "image": encoded_gif
            }
        )

        # Check ImgBB response
        if imgbb_response.status_code != 200:
            raise Exception(f"ImgBB upload failed: {imgbb_response.text}")

        imgbb_data = imgbb_response.json()
        if not imgbb_data.get('success'):
            raise Exception(f"ImgBB upload failed: {imgbb_data.get('error', 'Unknown error')}")

        gif_url = imgbb_data['data']['url']

        # Delete the local GIF file
        if os.path.exists(gif_path):
            os.remove(gif_path)

        return jsonify({
            'success': True,
            'gif_url': gif_url
        }), 200

    except Exception as e:
        # Clean up in case of error
        if os.path.exists(video_path):
            os.remove(video_path)
        if os.path.exists(gif_path):
            os.remove(gif_path)
        return jsonify({
            'success': False,
            'error': f'Processing failed: {str(e)}'
        }), 500

@app.route('/static/<path:path>')
def serve_static(path):
    return app.send_static_file(path)

if __name__ == '__main__':
    app.run(debug=False)