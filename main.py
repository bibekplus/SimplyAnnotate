from flask import Flask, jsonify, request, send_file, render_template
import json
import io
import csv
from datetime import datetime
import os

app = Flask(__name__, template_folder='templates')
DATA_FILE = 'data.json'
LABEL_FILE = 'labels.json'

# Initialize data files if not present
def initialize_data_files():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'w') as f:
            json.dump({'text_data': '', 'annotations': []}, f)
    if not os.path.exists(LABEL_FILE):
        with open(LABEL_FILE, 'w') as f:
            json.dump([
                {'label': 'PERSON', 'color': '#FFCDD2'},
                {'label': 'LOCATION', 'color': '#BBDEFB'},
                {'label': 'ORGANIZATION', 'color': '#C8E6C9'},
                {'label': 'DATE', 'color': '#FFE082'},
                {'label': 'MISC', 'color': '#E1BEE7'}
            ], f)
            #Might need to think about using SQLITE or something

initialize_data_files()

def load_data():
    with open(DATA_FILE, 'r') as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def load_labels():
    with open(LABEL_FILE, 'r') as f:
        return json.load(f)

def save_labels(labels):
    with open(LABEL_FILE, 'w') as f:
        json.dump(labels, f, indent=4)

def generate_timestamp():
    return datetime.now().strftime('%Y%m%d_%H%M%S')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/set_text', methods=['POST'])
def set_text():
    text_data = request.json.get('text_data', '')
    data = load_data()
    data['text_data'] = text_data
    data['annotations'] = []
    save_data(data)
    return jsonify({'status': 'success'})

@app.route('/get_annotations', methods=['GET'])
def get_annotations():
    data = load_data()
    return jsonify({'annotations': data['annotations']})

@app.route('/save_annotation', methods=['POST'])
def save_annotation():
    data = load_data()
    annotation = request.json
    text_length = len(data['text_data'])
    start = annotation.get('start')
    end = annotation.get('end')
    label = annotation.get('label')

    if not (isinstance(start, int) and isinstance(end, int)):
        return jsonify({'status': 'error', 'message': 'Invalid annotation indices'}), 400
    if not (0 <= start < text_length and 0 < end <= text_length):
        return jsonify({'status': 'error', 'message': 'Annotation indices out of bounds'}), 400

    # Remove any existing annotations that overlap with the new one
    data['annotations'] = [a for a in data['annotations'] if not (max(a['start'], start) < min(a['end'], end))]

    data['annotations'].append({
        'text': data['text_data'],
        'start': start,
        'end': end,
        'label': label
    })
    save_data(data)
    return jsonify({'status': 'success'})

@app.route('/delete_annotation', methods=['POST'])
def delete_annotation():
    data = load_data()
    annotation = request.json
    start = annotation.get('start')
    end = annotation.get('end')
    label = annotation.get('label')

    data['annotations'] = [a for a in data['annotations'] if not (
        a['start'] == start and a['end'] == end and a['label'] == label
    )]
    save_data(data)
    return jsonify({'status': 'success'})

@app.route('/reset_annotations', methods=['POST'])
def reset_annotations():
    data = load_data()
    data['text_data'] = ''
    data['annotations'] = []
    save_data(data)
    return jsonify({'status': 'success'})

@app.route('/export_annotations', methods=['POST'])
def export_annotations(): #Need to streamline this. This is too direct. May be it's a good thing? I'll worry about it later.
    data = load_data()
    annotations = data['annotations']
    format_type = request.json.get('format')

    if format_type == 'csv':
        return export_csv(annotations)
    elif format_type == 'json':
        return export_json(annotations)
    elif format_type == 'txt':
        return export_txt(annotations)
    elif format_type == 'conllu':
        return export_conllu(annotations)
    else:
        return jsonify({'status': 'error', 'message': 'Unsupported export format'}), 400

def export_csv(annotations):
    output = io.StringIO()
    fieldnames = ['ID', 'Text', 'Label']
    writer = csv.DictWriter(output, fieldnames=fieldnames)

    writer.writeheader()
    for idx, annotation in enumerate(annotations, start=1):
        writer.writerow({
            'ID': idx,
            'Text': annotation['text'][annotation['start']:annotation['end']],
            'Label': annotation['label']
        })
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'annotations_{generate_timestamp()}.csv'
    )

def export_json(annotations):
    output = io.StringIO()
    json.dump(annotations, output, indent=4)
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='application/json',
        as_attachment=True,
        download_name=f'annotations_{generate_timestamp()}.json'
    )

def export_txt(annotations): 
    output = io.StringIO()
    for idx, annotation in enumerate(annotations, start=1):
        output.write(f"{idx}\t{annotation['text'][annotation['start']:annotation['end']]}\t{annotation['label']}\n")
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/plain',
        as_attachment=True,
        download_name=f'annotations_{generate_timestamp()}.txt'
    )

#Might need to fix this
def export_conllu(annotations):
    output = io.StringIO()
    text_data = load_data()['text_data']
    tokens = text_data.strip().split()
    token_annotations = ['O'] * len(tokens)
    token_positions = []
    current_pos = 0
    for token in tokens:
        start = text_data.find(token, current_pos)
        end = start + len(token)
        token_positions.append((start, end))
        current_pos = end + 1  # +1 for space

    for annotation in annotations:
        start_char = annotation['start']
        end_char = annotation['end']
        label = annotation['label']
        for idx, (token_start, token_end) in enumerate(token_positions):
            if token_start >= start_char and token_end <= end_char:
                prefix = 'B' if token_start == start_char else 'I'
                token_annotations[idx] = f"{prefix}-{label}"

    for idx, (token, tag) in enumerate(zip(tokens, token_annotations), start=1):
        output.write(f"{idx}\t{token}\t_\t_\t_\t_\t_\t_\t_\t{tag}\n")
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/plain',
        as_attachment=True,
        download_name=f'annotations_{generate_timestamp()}.conllu'
    )

@app.route('/load_labels', methods=['GET'])
def load_labels_endpoint():
    labels = load_labels()
    return jsonify({'labels': labels})

@app.route('/save_label', methods=['POST'])
def save_label():
    labels = load_labels()
    label_data = request.json
    new_label = label_data.get('label')
    color = label_data.get('color', '#FFFFFF')
    if new_label and new_label not in [label['label'] for label in labels]:
        labels.append({'label': new_label, 'color': color})
        save_labels(labels)
        return jsonify({'status': 'success'})
    else:
        return jsonify({'status': 'error', 'message': 'Label already exists or invalid name.'}), 400

@app.route('/update_label', methods=['POST'])
def update_label():
    labels = load_labels()
    label_data = request.json
    for label in labels:
        if label['label'] == label_data['label']:
            label['color'] = label_data.get('color', label['color'])
            save_labels(labels)
            return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'Label not found.'}), 400

@app.route('/delete_label', methods=['POST'])
def delete_label():
    labels = load_labels()
    label_to_delete = request.json.get('label')
    labels = [label for label in labels if label['label'] != label_to_delete]
    save_labels(labels)
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    app.run(debug=True)
