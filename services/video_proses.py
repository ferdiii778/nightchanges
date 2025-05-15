# app/services/video_processor.py
import cv2
import os
from facenet_pytorch import MTCNN
from PIL import Image
from torchvision import transforms

device = 'cuda' if os.environ.get('USE_GPU', '1') == '1' and cv2.cuda.getCudaEnabledDeviceCount() > 0 else 'cpu'
mtcnn = MTCNN(keep_all=True, device=device)

transform = transforms.Compose([
    transforms.Resize((160, 160)),
    transforms.ToTensor(),
])

def extract_and_crop_faces(video_path: str, label: str, frame_skip: int = 5):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise Exception(f"Gagal membuka video: {video_path}")

    dataset_dir = f"dataset/{label}/cropped"
    os.makedirs(dataset_dir, exist_ok=True)

    frame_count = 0
    saved_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_count % frame_skip == 0:
            img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            boxes, _ = mtcnn.detect(img_rgb)

            if boxes is not None:
                for i, box in enumerate(boxes):
                    x1, y1, x2, y2 = [int(max(0, b)) for b in box]
                    face = img_rgb[y1:y2, x1:x2]

                    if face.size == 0:
                        continue

                    face_pil = Image.fromarray(face)
                    save_path = os.path.join(dataset_dir, f"{label}_{saved_count}.jpg")
                    face_pil.save(save_path)
                    saved_count += 1

        frame_count += 1

    cap.release()
    return saved_count
