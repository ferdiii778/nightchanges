# app/services/embedding_trainer.py
import os
import numpy as np
from PIL import Image
from facenet_pytorch import InceptionResnetV1
from torchvision import transforms
import torch
from glob import glob

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# Pretrained FaceNet
model = InceptionResnetV1(pretrained='vggface2').eval().to(device)

# Transform gambar
transform = transforms.Compose([
    transforms.Resize((160, 160)),
    transforms.ToTensor(),
    transforms.Normalize([0.5], [0.5])
])

def generate_embeddings(label: str, dataset_root="dataset", output_dir="embeddings"):
    cropped_dir = os.path.join(dataset_root, label, "cropped")
    os.makedirs(output_dir, exist_ok=True)

    embeddings = []
    labels = []

    # Baca semua gambar
    image_paths = glob(os.path.join(cropped_dir, "*.jpg"))

    for path in image_paths:
        img = Image.open(path).convert("RGB")
        tensor = transform(img).unsqueeze(0).to(device)

        with torch.no_grad():
            embedding = model(tensor).cpu().numpy()
            embeddings.append(embedding[0])
            labels.append(label)

    # Gabung dengan data sebelumnya (jika ada)
    emb_path = os.path.join(output_dir, "embeddings.npy")
    lbl_path = os.path.join(output_dir, "labels.npy")

    if os.path.exists(emb_path) and os.path.exists(lbl_path):
        prev_embeddings = np.load(emb_path)
        prev_labels = np.load(lbl_path)
        embeddings = np.vstack([prev_embeddings, embeddings])
        labels = np.concatenate([prev_labels, labels])
    else:
        embeddings = np.array(embeddings)
        labels = np.array(labels)

    # Simpan
    np.save(emb_path, embeddings)
    np.save(lbl_path, labels)

    return len(image_paths)
