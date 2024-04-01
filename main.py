from flask import Flask, render_template, request, jsonify, session
from flask_wtf import FlaskForm
from wtforms import FileField, SubmitField, StringField, HiddenField
from wtforms.validators import InputRequired
from werkzeug.utils import secure_filename
import webbrowser
import threading

from celery import Celery

import plotly
import plotly.graph_objs as go

import pandas as pd
import numpy as np
import cv2
import json
import os
import io
import shutil

import base64

from bsoid_utils import *
from tasks import save_images

cluster_range = [0.5, 1]

fps = 30     

# bsoid_umap/config/GLOBAL_CONFIG.py # edited 
UMAP_PARAMS = {
    'min_dist': 0.0,  # small value
    'random_state': 42,
}

HDBSCAN_PARAMS = {
    'min_samples': 1  # small value
}

app = Flask(__name__)
SECRET_KEY = os.urandom(32)
app.config['SECRET_KEY'] = 'secretkey'
app.config['TEMPLATES_AUTO_RELOAD'] = True

app.config['CELERY_BROKER_URL'] = 'http://127.0.0.1:5000/'
app.config['CELERY_RESULT_BACKEND'] = 'http://127.0.0.1:5000/'

celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

def open_browser():
    webbrowser.open_new('http://127.0.0.1:5000/')
    
class UploadForm(FlaskForm):
    action = HiddenField(default='upload')
    folder = StringField('Provide the path to the folder containing the csv and mp4 file:')
    submit = SubmitField('Generate UMAP Embedding')

class ClustersForm(FlaskForm):
    action = HiddenField(default='cluster')
    submit = SubmitField('Save images in clusters')

@app.route('/process_click_data', methods=['POST'])
def process_click_data():
    click_data = request.get_json()
    frame_number = click_data[0]['frame'] if click_data else None

    if frame_number is not None:
        mp4filepath = session.get('mp4', None)  # Get the mp4 object from the application context
        if mp4filepath is not None:
            mp4 = cv2.VideoCapture(mp4filepath)
            mp4.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ret, frame = mp4.read()
            mp4.release()

            if ret:
                # Convert the frame to a format that can be sent as a JSON response
                _, buffer = cv2.imencode('.jpg', frame)
                frame_data = base64.b64encode(buffer).decode('utf-8')

                return jsonify({'frame_data': frame_data})
            else:
                return jsonify({'error': 'Failed to retrieve frame'}), 400
        else:
            return jsonify({'error': 'Video not loaded'}), 400
    else:
        return jsonify({'error': 'Missing frame number'}), 400


@app.route('/', methods = ["GET","POST"])
@app.route('/home', methods = ["GET","POST"])
def home():
    plot = None
    folder_path = None
    uploadform = UploadForm()
    clustersform = ClustersForm()

    if uploadform.validate_on_submit() and uploadform.action.data == 'upload':

        folder_path = uploadform.folder.data
        session['folder_path'] = folder_path

        if not os.path.isdir('uploads'):
            os.mkdir('uploads')
        if not os.path.isdir(os.path.join('uploads', 'csvs')):
            os.mkdir(os.path.join('uploads', 'csvs'))
        if not os.path.isdir(os.path.join('uploads', 'videos')):
            os.mkdir(os.path.join('uploads', 'videos'))

        for filename in os.listdir(folder_path):
            if filename.endswith('.mp4'):
                mp4filepath = os.path.join('uploads', 'videos', filename)
                shutil.copyfile(os.path.join(folder_path,filename), mp4filepath)
                mp4 = cv2.VideoCapture(mp4filepath)
                session['mp4'] = mp4filepath

            elif filename.endswith('.csv'):
                csvfilepath = os.path.join('uploads', 'csvs', filename)
                shutil.copyfile(os.path.join(folder_path,filename), csvfilepath)
                file_j_df = pd.read_csv(csvfilepath, low_memory=False)          

        pose_chosen = []
    
        file_j_df_array = np.array(file_j_df)

        p = st.multiselect('Identified __pose__ to include:', [*file_j_df_array[0, 1:-1:3]], [*file_j_df_array[0, 1:-1:3]])
        for a in p:
            index = [i for i, s in enumerate(file_j_df_array[0, 1:]) if a in s]
            if not index in pose_chosen:
                pose_chosen += index
        pose_chosen.sort()

        file_j_processed, p_sub_threshold = adp_filt(file_j_df, pose_chosen)
        file_j_processed = file_j_processed.reshape((1, file_j_processed.shape[0], file_j_processed.shape[1]))

        scaled_features, features, frame_mapping = compute(file_j_processed, fps)

        train_size = subsample(file_j_processed, fps)

        sampled_embeddings = learn_embeddings(scaled_features, features, UMAP_PARAMS, train_size)

        assignments = hierarchy(cluster_range, sampled_embeddings, HDBSCAN_PARAMS)

        sampled_embeddings_filtered = sampled_embeddings[assignments>=0]
        assignments_filtered = assignments[assignments>=0]    
        frame_mapping_filtered = frame_mapping[assignments>=0] 

        session['assignments_filtered'] = assignments_filtered.tolist()
        session['frame_mapping_filtered'] = frame_mapping_filtered.tolist()

        plot = create_plotly(sampled_embeddings_filtered, assignments_filtered, filename, frame_mapping_filtered)
        session['plot'] = plot

    elif clustersform.validate_on_submit() and clustersform.action.data == 'cluster':
        
        mp4filepath = session.get('mp4', None)
        folder_path = session.get('folder_path', None)
        frame_mapping_filtered = session.get('frame_mapping_filtered')
        assignments_filtered = session.get('assignments_filtered')

        save_images(mp4filepath, folder_path, frame_mapping_filtered, assignments_filtered)
    
    return render_template('index.html', uploadform=uploadform, clustersform=clustersform, graphJSON=session.get('plot', None))

if __name__ == '__main__':
    threading.Thread(target=open_browser).start()
    app.run(debug = True)