import itertools
import numpy as np
import pandas as pd
import math 
from tqdm import tqdm
import joblib
import os
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from psutil import virtual_memory
from umap import UMAP
import hdbscan

#from cuml.cluster import hdbscan
#from cuml.manifold import UMAP 

import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.axes._axes import _log as matplotlib_axes_logger
matplotlib_axes_logger.setLevel('ERROR')

import streamlit as st

import plotly.express as px
import plotly 

import json

import random

# bsoid_app/bsoid_utilities/likelihoodprocessing.py
def boxcar_center(a, n):
    a1 = pd.Series(a)
    moving_avg = np.array(a1.rolling(window=n, min_periods=1, center=True).mean())

    return moving_avg

# bsoid_app/bsoid_utilities/likelihoodprocessing.py
def adp_filt(currdf: object, pose):
    lIndex = []
    xIndex = []
    yIndex = []
    currdf = np.array(currdf[1:])
    for header in pose:
        if currdf[0][header + 1] == "likelihood":
            lIndex.append(header)
        elif currdf[0][header + 1] == "x":
            xIndex.append(header)
        elif currdf[0][header + 1] == "y":
            yIndex.append(header)
    curr_df1 = currdf[:, 1:]
    datax = curr_df1[1:, np.array(xIndex)]
    datay = curr_df1[1:, np.array(yIndex)]
    data_lh = curr_df1[1:, np.array(lIndex)]
    currdf_filt = np.zeros((datax.shape[0], (datax.shape[1]) * 2))
    perc_rect = []
    for i in range(data_lh.shape[1]):
        perc_rect.append(0)
    for x in tqdm(range(data_lh.shape[1])):
        a, b = np.histogram(data_lh[1:, x].astype(float))
        rise_a = np.where(np.diff(a) >= 0)
        if rise_a[0][0] > 1:
            llh = b[rise_a[0][0]]
        else:
            llh = b[rise_a[0][1]]
        data_lh_float = data_lh[:, x].astype(float)
        perc_rect[x] = np.sum(data_lh_float < llh) / data_lh.shape[0]
        currdf_filt[0, (2 * x):(2 * x + 2)] = np.hstack([datax[0, x], datay[0, x]])
        for i in range(1, data_lh.shape[0]):
            if data_lh_float[i] < llh:
                currdf_filt[i, (2 * x):(2 * x + 2)] = currdf_filt[i - 1, (2 * x):(2 * x + 2)]
            else:
                currdf_filt[i, (2 * x):(2 * x + 2)] = np.hstack([datax[i, x], datay[i, x]])
    currdf_filt = np.array(currdf_filt)
    currdf_filt = currdf_filt.astype(float)
    return currdf_filt, perc_rect

# bsoid_app/bsoid_utilities/load_workspace.py
def load_feats(path, name):
    with open(os.path.join(path, str.join('', (name, '_feats.sav'))), 'rb') as fr:
        data = joblib.load(fr)
    return [i for i in data]

# bsoid_app/extract_features.py # edited
def compute(processed_input_data, file_j_df_array, framerate):
        #if st.button("__Extract Features__"):
        #    funfacts = randfacts.getFact()
        #    st.info(str.join('', ('Extracting... Here is a random fact: ', funfacts)))
        #try:
        #    [features, scaled_features] = load_feats(working_dir, prefix)
        #except:
        window = int(np.round(0.05 / (1 / framerate)) * 2 - 1)
        f = []
        my_bar = st.progress(0)
        for n in range(len(processed_input_data)):
            data_n_len = len(processed_input_data[n])
            dxy_list = []
            disp_list = []

            # (MB, 5/21/2024): calculate the interframe distance of the body parts from frame n to frame n + 1 

            for r in range(data_n_len):
                if r < data_n_len - 1:
                    disp = []
                    for c in range(0, processed_input_data[n].shape[1], 2):
                        
                        disp.append(
                            np.linalg.norm(processed_input_data[n][r + 1, c:c + 2] -
                                        processed_input_data[n][r, c:c + 2]))
                    disp_list.append(disp) # (MB, 5/21/2024): append the interframe distances for each row to the big list
                
                # (MB, 5/21/2024): calculate the pairwise distance vectors from each body part to each of the other body parts

                dxy = []
                for i, j in itertools.combinations(range(0, processed_input_data[n].shape[1], 2), 2):
                    dxy.append(processed_input_data[n][r, i:i + 2] -
                            processed_input_data[n][r, j:j + 2])
                
                dxy_list.append(dxy) # (MB, 5/21/2024): append the pairwise distance vectors for each row to the big list
            disp_r = np.array(disp_list)
            dxy_r = np.array(dxy_list)
            disp_boxcar = []
            dxy_eu = np.zeros([data_n_len, dxy_r.shape[1]])
            ang = np.zeros([data_n_len - 1, dxy_r.shape[1]])
            dxy_boxcar = []
            ang_boxcar = []

            # (MB, 5/21/2024): average the interframe distance values with a rolling average with a window size of 3 ( window = int(np.round(0.05 / (1 / framerate)) * 2 - 1) )

            for l in range(disp_r.shape[1]):
                disp_boxcar.append(boxcar_center(disp_r[:, l], window))
            
            
            for k in range(dxy_r.shape[1]): # (MB, 5/21/2024): for each column of dxr
                for kk in range(data_n_len): # (MB, 5/21/2024): for each row
                    dxy_eu[kk, k] = np.linalg.norm(dxy_r[kk, k, :]) # (MB, 5/21/2024): calculate the pairwise euclidean distance
                    if kk < data_n_len - 1:
                        
                        # (MB, 5/21/2024): calculate the interframe angles of the body parts 
                        b_3d = np.hstack([dxy_r[kk + 1, k, :], 0])
                        a_3d = np.hstack([dxy_r[kk, k, :], 0])
                        c = np.cross(b_3d, a_3d)
                        ang[kk, k] = np.dot(np.dot(np.sign(c[2]), 180) / np.pi,
                                            math.atan2(np.linalg.norm(c),
                                                    np.dot(dxy_r[kk, k, :], dxy_r[kk + 1, k, :])))
                dxy_boxcar.append(boxcar_center(dxy_eu[:, k], window))
                ang_boxcar.append(boxcar_center(ang[:, k], window))
            disp_feat = np.array(disp_boxcar)
            dxy_feat = np.array(dxy_boxcar)
            ang_feat = np.array(ang_boxcar)
            f.append(np.vstack((dxy_feat[:, 1:], ang_feat, disp_feat)))
            my_bar.progress(round((n + 1) / len(processed_input_data) * 100))
        
        frame_mapping  = []
        frame_number = []

        # (MB, 5/21/2024): calculate the mean of the distance features and the sum of the angle features in a window size of 3

        for m in range(0, len(f)):
            f_integrated = np.zeros(len(processed_input_data[m]))
            for k in range(round(framerate / 10), len(f[m][0]), round(framerate / 10)):
                print(k)
                frame_number.append(k-1)
                frame_mapping.append(file_j_df_array[k-1+2][0])
                if k > round(framerate / 10):
                    f_integrated = np.concatenate(
                        (f_integrated.reshape(f_integrated.shape[0], f_integrated.shape[1]),
                        np.hstack((np.mean((f[m][0:dxy_feat.shape[0],
                                            range(k - round(framerate / 10), k)]), axis=1),
                                    np.sum((f[m][dxy_feat.shape[0]:f[m].shape[0],
                                            range(k - round(framerate / 10), k)]), axis=1)
                                    )).reshape(len(f[0]), 1)), axis=1
                    )
                else:
                    f_integrated = np.hstack(
                        (np.mean((f[m][0:dxy_feat.shape[0], range(k - round(framerate / 10), k)]), axis=1),
                        np.sum((f[m][dxy_feat.shape[0]:f[m].shape[0],
                                range(k - round(framerate / 10), k)]), axis=1))).reshape(len(f[0]), 1)
            if m > 0:
                features = np.concatenate((features, f_integrated), axis=1)
                scaler = StandardScaler()
                scaler.fit(f_integrated.T)
                scaled_f_integrated = scaler.transform(f_integrated.T).T
                scaled_features = np.concatenate((scaled_features, scaled_f_integrated), axis=1)
            else:
                features = f_integrated
                scaler = StandardScaler()
                scaler.fit(f_integrated.T)
                scaled_f_integrated = scaler.transform(f_integrated.T).T
                scaled_features = scaled_f_integrated
        features = np.array(features)
        scaled_features = np.array(scaled_features)

        frame_mapping = np.array(frame_mapping)
        frame_number = np.array(frame_number)

        return scaled_features, features, frame_mapping, frame_number

# bsoid_app/extract_features.py # edited
def subsample(processed_input_data, framerate, training_fraction, scaled_features, frame_mapping, frame_number):
        data_size = 0
        for n in range(len(processed_input_data)):
            data_size += len(range(round(framerate / 10), processed_input_data[n].shape[0],
                                   round(framerate / 10)))
        fraction = training_fraction #st.number_input('Enter training input __fraction__ (do not change this value if you wish '
                   #                'to generate the side-by-side video seen on our GitHub page):',
                   #                min_value=0.1, max_value=1.0, value=1.0)
        if fraction == 1.0:
            train_size = data_size
        else:
            train_size = int(data_size * fraction)
        #st.markdown('You have opted to train on a cumulative of **{} minutes** total. '
        #            'If this does not sound right, the framerate might be wrong.'.format(train_size / 600))

        input_feats = scaled_features.T

        if train_size > input_feats.shape[0]:
            train_size = input_feats.shape[0]

        np.random.seed(0)
        random_choice = np.random.choice(input_feats.shape[0], train_size, replace=False)
        
        sampled_input_feats = input_feats[random_choice]
        sampled_frame_mapping = frame_mapping[random_choice]
        sampled_frame_number = frame_number[random_choice]

        return sampled_input_feats, sampled_frame_mapping, sampled_frame_number

    # features_transposed = features.T
    # np.random.seed(0)
    # sampled_features = features_transposed[np.random.choice(features_transposed.shape[0],
    #                                                                     train_size, replace=False)]
    
# bsoid_app/extract_features.py # edited
def learn_embeddings(UMAP_PARAMS, data):

    scaled_features_list = []
    sampled_input_feats_list = []
    
    basename_mappings = []
    csv_mappings = []
    frame_mappings = []
    frame_numbers = []

    m = 0 

    basename_indices = []
    for basename, content in data['files'].items():
        sampled_input_feats_list.append(content['sampled_input_feats'])
        scaled_features_list.append(content['scaled_features'])
        
        csv_name = os.path.basename(content["csv_path"])

        num_samples = len(content['sampled_input_feats'])
        basename_repeated = [basename] * num_samples
        csv_name_repeated = [csv_name] * num_samples

        basename_mappings.extend(basename_repeated)
        csv_mappings.extend(csv_name_repeated)
        frame_mappings.extend(content['sampled_frame_mapping'])
        frame_numbers.extend(content['sampled_frame_number'])

        f_integrated = content['features']

        if m > 0:
            features = np.concatenate((features, f_integrated), axis=1)
            scaler = StandardScaler()
            scaler.fit(f_integrated.T)
            scaled_f_integrated = scaler.transform(f_integrated.T).T
            scaled_features = np.concatenate((scaled_features, scaled_f_integrated), axis=1)
        else:
            features = f_integrated
            scaler = StandardScaler()
            scaler.fit(f_integrated.T)
            scaled_f_integrated = scaler.transform(f_integrated.T).T
            scaled_features = scaled_f_integrated
        m = m + 1
    
    concatenated_sampled_features = np.vstack(sampled_input_feats_list)
    concatenated_scaled_features = np.hstack(scaled_features_list)

    
    input_feats = scaled_features.T

    pca = PCA()
    pca.fit(input_feats)
    num_dimensions = np.argwhere(np.cumsum(pca.explained_variance_ratio_) >= 0.7)[0][0] + 1

    np.random.seed(0)
    sampled_input_feats = input_feats[np.random.choice(input_feats.shape[0], input_feats.shape[0], replace=False)]
 
    learned_embeddings = UMAP(n_neighbors=60, n_components=num_dimensions,
                                                **UMAP_PARAMS).fit(sampled_input_feats)

    sampled_embeddings = learned_embeddings.embedding_

    print("input_feats: ", np.shape(input_feats))
    print("sampled_input_feats: ", np.shape(sampled_input_feats))
    print("sampled_embeddings: ", np.shape(sampled_embeddings))
    print("num_dimensions: ", num_dimensions)

    current_index = 0
    for basename, count in basename_indices:
        # Slice the learned embeddings using the count
        data['files'][basename]['sampled_embeddings'] = sampled_embeddings[current_index:current_index + count]
        current_index += count

    return sampled_embeddings, data, basename_mappings, csv_mappings, frame_mappings, frame_numbers, scaled_features

# bsoid_app/clustering.py # edited 
def hierarchy(cluster_range, sampled_embeddings, HDBSCAN_PARAMS):
    max_num_clusters = -np.infty
    num_clusters = []
    min_cluster_size = np.linspace(cluster_range[0], cluster_range[1], 25)

    for min_c in min_cluster_size:
        min_size = int(round(min_c * 0.01 * sampled_embeddings.shape[0])) if int(round(min_c * 0.01 * sampled_embeddings.shape[0])) > 1 else 2 # figure this out 3/13/24
        learned_hierarchy = hdbscan.HDBSCAN(
            prediction_data=True, min_cluster_size=min_size,
            **HDBSCAN_PARAMS).fit(sampled_embeddings)
        num_clusters.append(len(np.unique(learned_hierarchy.labels_)))
        if num_clusters[-1] > max_num_clusters:
            max_num_clusters = num_clusters[-1]
            retained_hierarchy = learned_hierarchy
    assignments = retained_hierarchy.labels_
    assign_prob = hdbscan.all_points_membership_vectors(retained_hierarchy)
    soft_assignments = np.argmax(assign_prob, axis=1)

    current_index = 0

    return assignments


# bsoid_app/bsoid_utilities/visuals.py
#def plot_classes(data, assignments):
#   """ Plot umap_embeddings for HDBSCAN assignments
#    :param data: 2D array, umap_embeddings
#    :param assignments: 1D array, HDBSCAN assignments
#    """
def plot_classes(sampled_embeddings, assignments, file):
    sampled_embeddings_filtered = sampled_embeddings[assignments>=0]
    assignments_filtered = assignments[assignments>=0]    
    uk = list(np.unique(assignments_filtered))
    R = np.linspace(0, 1, len(uk))
    cmap = plt.cm.get_cmap("Spectral")(R)
    umap_x, umap_y, umap_z = sampled_embeddings_filtered[:, 0], sampled_embeddings_filtered[:, 1], sampled_embeddings_filtered[:, 2]
    fig = plt.figure(figsize=(9, 9))
    ax = fig.add_subplot(111, projection='3d')
    for g in np.unique(assignments_filtered):
        idx = np.where(np.array(assignments_filtered) == g)
        ax.scatter(umap_x[idx], umap_y[idx], umap_z[idx], c=cmap[g],
                    label=g, s=0.4, marker='o', alpha=0.8)
    ax.set_xlabel('Dim. 1')
    ax.set_ylabel('Dim. 2')
    ax.set_zlabel('Dim. 3')
    plt.title(file.replace(".csv", ""))
    plt.legend(ncol=3, markerscale=6)
    return fig

def create_plotly(sampled_embeddings, assignments, frame_mappings, frame_numbers, basename_mappings, csv_mappings):
    # Initialize lists to hold all the frame mappings, frame numbers, and basenames
    all_frame_mapping = []
    all_frame_number = []
    all_basename = []

    # Aggregate frame mappings and numbers for each basename in the data dictionary
    # for basename, info in data.items():
    #     num_points = len(info['sampled_frame_mapping'])
    #     all_frame_mapping.extend(info['sampled_frame_mapping'])
    #     all_frame_number.extend(info['sampled_frame_number'])
    #     all_basename.extend([basename] * num_points)

    # Create the DataFrame including basenames
    df = pd.DataFrame({
        'x': sampled_embeddings[:, 0],
        'y': sampled_embeddings[:, 1],
        'z': sampled_embeddings[:, 2],
        'assignments': assignments.astype(str),
        'frame_mappings': frame_mappings,
        'frame_numbers': frame_numbers,
        'basenames': basename_mappings,
        'csvs': csv_mappings
    })

    # Create a unique color for each cluster assignment
    unique_assignments = np.unique(assignments)
    num_unique_assignments = len(unique_assignments)
    colors = ["#{:06x}".format(random.randint(0, 0xFFFFFF)) for _ in range(num_unique_assignments)]

    # Create the 3D scatter plot with Plotly
    fig = px.scatter_3d(df, x='x', y='y', z='z', color='assignments',
                        labels={'assignments': 'Assignment'},
                        custom_data=['frame_mappings', 'frame_numbers', 'assignments', 'basenames', 'csvs'],
                        color_discrete_sequence=colors)

    # Customize marker size and hover template
    fig.update_traces(marker_size=1)
    fig.update_traces(hovertemplate="<br>".join([
        "Frame: %{customdata[0]}",
        "Basename: %{customdata[3]}"
    ]))

    return fig