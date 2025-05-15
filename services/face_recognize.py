# app/services/face_recognizer.py
import cv2
import numpy as np
from facenet_pytorch import MTCNN, InceptionResnetV1
from sklearn.metrics.pairwise import cosine_similarity
import torch

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
mtcnn = MTCNN(keep_all=True, device=device)
facenet = InceptionResnetV1(pretrained='vggface2').eval().to(device)

def start_monitoring(source=0, threshold=0.75):
    embeddings = np.load("embeddings/embeddings.npy")
    labels = np.load("embeddings/labels.npy")

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        return "[ERROR] Tidak dapat membuka stream"

    print("[INFO] Monitoring aktif. Tekan 'q' untuk berhenti.")
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        boxes, _ = mtcnn.detect(img_rgb)

        if boxes is not None:
            for box in boxes:
                x1, y1, x2, y2 = [int(b) for b in box]
                face = img_rgb[y1:y2, x1:x2]

                if face.size == 0:
                    continue

                face_tensor = mtcnn.extract(frame, [box], save_path=None)[0].unsqueeze(0).to(device)
                with torch.no_grad():
                    emb = facenet(face_tensor).cpu().numpy()

                sims = cosine_similarity(emb, embeddings)[0]
                score = np.max(sims)
                best_idx = np.argmax(sims)

                if score >= threshold:
                    name = labels[best_idx]
                    color = (0, 255, 0)
                else:
                    name = "Unknown"
                    color = (0, 0, 255)

                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(frame, f"{name} ({score:.2f})", (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        cv2.imshow("Monitoring CCTV", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    return "Monitoring selesai"
