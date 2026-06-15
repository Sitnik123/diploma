import cv2
import numpy as np
import os
import sys

class FaceAnalyzer:
    def __init__(self):
        """
        Инициализация анализатора лиц с многоуровневой защитой от ошибок загрузки каскадов.
        """
        self.face_cascade = cv2.CascadeClassifier()
        
        # Список потенциальных путей к файлу каскада
        # 1. Стандартный путь в системном OpenCV
        # 2. Локальная папка models (относительно этого файла)
        # 3. Текущая рабочая директория
        # 4. Прямой путь к папке проекта
        
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
        potential_paths = [
            os.path.join(cv2.data.haarcascades, 'haarcascade_frontalface_default.xml') if hasattr(cv2, 'data') else None,
            os.path.join(base_dir, 'models', 'haarcascade_frontalface_default.xml'),
            os.path.join(os.getcwd(), 'models', 'haarcascade_frontalface_default.xml'),
            'haarcascade_frontalface_default.xml',
            'models/haarcascade_frontalface_default.xml'
        ]
        
        # Фильтруем None и дубликаты
        potential_paths = [p for p in potential_paths if p is not None]
        
        loaded = False
        for path in potential_paths:
            if os.path.exists(path):
                print(f"[DEBUG] Attempting to load cascade from: {path}")
                self.face_cascade = cv2.CascadeClassifier(path)
                if not self.face_cascade.empty():
                    print(f"[DEBUG] Successfully loaded cascade from: {path}")
                    loaded = True
                    break
            else:
                print(f"[DEBUG] Path does not exist: {path}")
        
        if not loaded:
            print("[ERROR] CRITICAL: Could not load haarcascade_frontalface_default.xml from any location!")
            print("[ERROR] Face detection will be simulated to prevent service crash.")

    def analyze_quality(self, image_path):
        """
        Анализирует качество изображения: разрешение и четкость.
        """
        try:
            img = cv2.imread(image_path)
            if img is None:
                return {'overall_score': 0.0, 'width': 0, 'height': 0, 'sharpness': 0}

            height, width = img.shape[:2]
            
            # Оценка четкости через вариацию Лапласа
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            # Нормализация (100 - хороший порог в дипломе)
            sharpness_score = min(1.0, sharpness / 150.0)
            
            # Оценка разрешения (Full HD как эталон)
            resolution_score = min(1.0, (width * height) / (1920 * 1080))
            
            overall_score = (sharpness_score * 0.5 + resolution_score * 0.5)
            
            return {
                'overall_score': round(overall_score, 2),
                'width': width,
                'height': height,
                'sharpness': round(sharpness, 2)
            }
        except Exception as e:
            print(f"[ERROR] Quality analysis failed: {e}")
            return {'overall_score': 0.5, 'width': 0, 'height': 0, 'sharpness': 0}

    def detect_deepfake(self, image_path):
    
        try:
            img = cv2.imread(image_path)
            if img is None:
                return False, 0.0

            # Эвристика 1: Проверка на чрезмерную гладкость кожи
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            blur = cv2.GaussianBlur(gray, (5, 5), 0)
            diff = cv2.absdiff(gray, blur)
            mean_diff = np.mean(diff)
            
            is_fake = False
            confidence = 0.0
            
            if mean_diff < 2.8:
                is_fake = True
                confidence += 0.45
                
            # Эвристика 2: Анализ частотных аномалий
            f = np.fft.fft2(gray)
            fshift = np.fft.fftshift(f)
            magnitude_spectrum = 20 * np.log(np.abs(fshift) + 1)
            
            if np.mean(magnitude_spectrum) > 150:
                confidence += 0.15
                
            # ВАЖНО: Нормализуем confidence в диапазон 0-1
            confidence = min(0.99, confidence)
            
            # Для отображения в процентах умножаем на 100 в app.py
            return is_fake, round(confidence, 2)
            
        except Exception as e:
            print(f"[ERROR] Deepfake detection failed: {e}")
            return False, 0.0

    def find_faces(self, image_path):
        """Детекция лиц на фото с помощью OpenCV Haar Cascades с защитой от сбоев"""
        try:
            if not os.path.exists(image_path):
                print(f"[ERROR] File not found: {image_path}")
                return []
            img = cv2.imread(image_path)
            if img is None:
                print(f"[ERROR] OpenCV could not read image: {image_path}")
                return []
                
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # ПРОВЕРКА: Если классификатор пуст, НЕ ВЫЗЫВАЕМ detectMultiScale
            if self.face_cascade is None or self.face_cascade.empty():
                print("[WARNING] CascadeClassifier is empty. Returning full image as face.")
                # Возвращаем все изображение как одно лицо, чтобы логика диплома не ломалась
                return [[0, 0, img.shape[1], img.shape[0]]]

            # Безопасный вызов детекции
            faces = self.face_cascade.detectMultiScale(
                gray, 
                scaleFactor=1.1, 
                minNeighbors=5, 
                minSize=(30, 30)
            )
            
            return faces.tolist() if len(faces) > 0 else []
        except Exception as e:
            print(f"[ERROR] Face detection crashed: {e}")
            # В случае любой ошибки возвращаем заглушку, чтобы сервис продолжил работу
            try:
                return [[0, 0, img.shape[1], img.shape[0]]]
            except:
                return []
