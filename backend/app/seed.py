from sqlalchemy import func, select
from sqlalchemy.orm import Session
from .models import Destination

# Data awal: harga tiket hanya perkiraan untuk prototipe.
DATA = [
    ("Pura Tanah Lot", "Budaya", "Bali", 75000, -8.6212, 115.0868),
    ("Pantai Kuta", "Alam", "Bali", 0, -8.7184, 115.1686),
    ("Tegalalang Rice Terrace", "Alam", "Bali", 20000, -8.4312, 115.2796),
    ("Pura Uluwatu", "Budaya", "Bali", 50000, -8.8291, 115.0849),
    ("Ubud Monkey Forest", "Alam", "Bali", 100000, -8.5188, 115.2588),
    ("Candi Prambanan", "Sejarah", "Yogyakarta", 50000, -7.7520, 110.4915),
    ("Keraton Yogyakarta", "Budaya", "Yogyakarta", 15000, -7.8053, 110.3642),
    ("Malioboro", "Kuliner", "Yogyakarta", 0, -7.7926, 110.3658),
    ("Taman Sari", "Sejarah", "Yogyakarta", 15000, -7.8100, 110.3590),
    ("Candi Borobudur", "Sejarah", "Yogyakarta", 50000, -7.6079, 110.2038),
    ("Pulau Padar", "Alam", "Labuan Bajo", 100000, -8.6528, 119.5876),
    ("Pulau Komodo", "Alam", "Labuan Bajo", 150000, -8.5500, 119.4833),
    ("Pink Beach", "Alam", "Labuan Bajo", 50000, -8.5961, 119.4500),
    ("Pulau Derawan", "Alam", "Derawan", 20000, 2.2800, 118.2400),
    ("Pulau Kakaban", "Alam", "Derawan", 50000, 2.1500, 118.4700),
]


def seed(db: Session):
    if db.scalar(select(func.count(Destination.id))):
        return
    db.add_all(Destination(name=n, category=c, location=l, price_estimate=p, lat=la, lng=lo,
                           description=f"{n} - {c} di {l}") for n, c, l, p, la, lo in DATA)
    db.commit()
