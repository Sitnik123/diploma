from flask import Flask, render_template, request, jsonify
import os
from werkzeug.utils import secure_filename
import uuid
from detector import FaceAnalyzer
from Search_engine import SearchEngine
from Scoring_engine import DeepfakeVulnerabilityScorer
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

analyzer = FaceAnalyzer()
search_engine = SearchEngine()
scorer = DeepfakeVulnerabilityScorer()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    if 'photo' not in request.files:
        return jsonify({'error': 'Файл не загружен'}), 400
    
    file = request.files['photo']
    name = request.form.get('name', 'Неизвестный')
    position = request.form.get('position', 'Сотрудник')
    
    if file.filename == '':
        return jsonify({'error': 'Файл не выбран'}), 400

    filename = secure_filename(f"{uuid.uuid4()}_{file.filename}")
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    try:
        # 1. Анализ лица и качества
        faces = analyzer.find_faces(filepath)
        if not faces:
            return jsonify({'error': 'Лицо не обнаружено на фотографии'}), 400
        
        quality = analyzer.analyze_quality(filepath)
        is_deepfake, confidence = analyzer.detect_deepfake(filepath)
        
        # 2. Поиск в интернете через Apify
        # Ищем похожие изображения и упоминания имени
        search_results = search_engine.search_by_name(name)
        image_results = search_engine.search_images(name, local_path=filepath)
        stats = search_engine.get_statistics(image_results if image_results else search_results)
        
        # 3. Расчет DFVS
        report = scorer.calculate_dfvs(
            photo_count=stats['count'],
            quality_metrics=quality,
            sources=image_results if image_results else search_results,
            position=position,
            name=name
        )
        
        # 4. Формирование ответа
        final_response = {
            'dfvs_score': report['dfvs_score'],
            'risk_level': report['risk_level'],
            'recommendation': report['recommendation'],
            'components': report['components'],
            'is_deepfake': is_deepfake,
            'deepfake_confidence': round(confidence * 100, 1),
            'search_stats': stats,
            'search_results': search_results[:10],
            'image_results': image_results[:10],
            'photo_url': f"/static/uploads/{filename}",
            'quality_metrics': {
                'resolution': f"{quality.get('width')}x{quality.get('height')}",
                'sharpness': 'Высокая' if quality.get('sharpness', 0) > 100 else 'Средняя' if quality.get('sharpness', 0) > 50 else 'Низкая',
                'score': round(quality.get('overall_score', 0) * 10, 1)
            }
        }
        
        return jsonify(final_response)

    except Exception as e:
        print(f"[ERROR] Analysis failed: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
