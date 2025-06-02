from flask import Flask, send_file, request
from flask_restx import Api, Resource, fields
import cv2
from PIL import Image
import os
import uuid
from werkzeug.utils import secure_filename
import time
import errno
import numpy as np

app = Flask(__name__)
api = Api(app, version='1.0', title='Video to GIF Converter API',
          description='API to convert video files to GIFs')

# Define the namespace
ns = api.namespace('converter', description='Video to GIF conversion operations')

# Define the form parameters for Swagger
video_field = ns.parser()
video_field.add_argument('video', type='file', location='files', required=True, help='Video file to convert (e.g., .mp4, .avi)')
video_field.add_argument('fps', type=int, location='form', default=10, help='Frames per second for the GIF (e.g., 10)')
video_field.add_argument('scale', type=float, location='form', default=0.5, help='Scale factor for GIF resolution (0.0 to 1.0, e.g., 0.5)')

# Directory to store temporary files
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def safe_remove(file_path, retries=3, delay=0.5):
    """Attempt to remove a file with retries in case it's still in use."""
    for attempt in range(retries):
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            return True
        except OSError as e:
            if e.errno != errno.EACCES:  # errno.EACCES is "permission denied"
                raise  # Re-raise if it's a different error
            if attempt < retries - 1:  # Don't sleep on the last attempt
                time.sleep(delay)
    return False

def resize_frame(frame, scale):
    """Resize a frame (numpy array) by the given scale factor using OpenCV."""
    if scale == 1.0:
        return frame
    height, width = frame.shape[:2]
    new_height, new_width = int(height * scale), int(width * scale)
    resized = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)
    return resized

def convert_video_to_gif(input_path, output_path, fps=10, scale=0.5):
    try:
        # Open the video file with OpenCV
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            return False, "Could not open video file"

        # Get the original FPS of the video
        original_fps = cap.get(cv2.CAP_PROP_FPS)
        if original_fps <= 0:
            original_fps = 30  # Default to 30 if FPS cannot be determined

        # Calculate frame step to achieve desired FPS
        frame_step = max(1, int(original_fps / fps))

        # Read video frames
        frames = []
        frame_count = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_count % frame_step == 0:  # Sample frames based on desired FPS
                # Resize frame
                resized_frame = resize_frame(frame, scale)
                # Convert BGR (OpenCV format) to RGB (PIL format)
                rgb_frame = cv2.cvtColor(resized_frame, cv2.COLOR_BGR2RGB)
                # Convert to PIL Image
                pil_image = Image.fromarray(rgb_frame)
                frames.append(pil_image)

            frame_count += 1

        # Release the video capture object
        cap.release()

        if not frames:
            return False, "No frames extracted from video"

        # Calculate duration per frame in milliseconds
        duration_per_frame = 1000 / fps  # in milliseconds

        # Save frames as GIF using PIL
        frames[0].save(
            output_path,
            save_all=True,
            append_images=frames[1:],
            duration=duration_per_frame,
            loop=0
        )

        return True, "Conversion successful"
    except Exception as e:
        return False, f"Error converting video to GIF: {str(e)}"
    finally:
        # Ensure the video capture is released even if an error occurs
        if 'cap' in locals() and cap.isOpened():
            cap.release()

@ns.route('/video-to-gif')
class VideoToGif(Resource):
    @ns.expect(video_field)
    @ns.response(200, 'GIF generated successfully', content_type='image/gif')
    @ns.response(400, 'Invalid input')
    @ns.response(500, 'Server error')
    def post(self):
        if 'video' not in request.files:
            return {'message': 'No video file provided'}, 400

        video_file = request.files['video']
        if video_file.filename == '':
            return {'message': 'No file selected'}, 400

        # Securely save the uploaded file
        filename = secure_filename(video_file.filename)
        unique_id = str(uuid.uuid4())
        input_path = os.path.join(UPLOAD_FOLDER, f"{unique_id}_{filename}")
        video_file.save(input_path)

        # Get optional parameters
        fps = int(request.form.get('fps', 10))
        scale = float(request.form.get('scale', 0.5))

        # Validate parameters
        if fps <= 0 or scale <= 0:
            safe_remove(input_path)
            return {'message': 'FPS and scale must be positive'}, 400

        # Generate output path
        output_filename = f"{unique_id}_output.gif"
        output_path = os.path.join(OUTPUT_FOLDER, output_filename)

        # Perform conversion
        success, message = convert_video_to_gif(input_path, output_path, fps, scale)
        
        # Clean up input file with retry mechanism
        if not safe_remove(input_path):
            return {'message': 'Failed to clean up input file due to access issue'}, 500

        if not success:
            return {'message': message}, 500

        # Send the GIF file
        try:
            response = send_file(output_path, mimetype='image/gif', as_attachment=True, download_name='output.gif')
            # Clean up output file after sending
            if not safe_remove(output_path):
                return {'message': 'Failed to clean up output file due to access issue'}, 500
            return response
        except Exception as e:
            return {'message': f"Error sending GIF: {str(e)}"}, 500

# Add the namespace to the API
api.add_namespace(ns)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)