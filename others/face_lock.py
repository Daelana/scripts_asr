#!/usr/bin/env python3
#------------------------------------------------------
# Titre: Face recognition et prise de photos
# Version : 1.0
# Auteur : Alexia ROUSSET
# Date : 24/04/2026
#------------------------------------------------------

# à faire qu'une fois pour enregistrer son visage, lancer la reconnaissance et importer les modules
"""
FaceLock — pip install opencv-python face_recognition numpy
  python face_lock.py enroll   (première fois)
  python face_lock.py start
"""
import cv2, face_recognition, numpy as np, pickle, os, sys, time, threading
from datetime import datetime
from pathlib import Path

CAM, TIMEOUT, HOLD, TOL = 0, 3.0, 1.5, 0.5
DB, FOLDER = "faces.pkl", "intruders"

# ── DB ───────────────────────────────────────
# si le fichier existe, charge les visages enregistrés, sinon retourne une liste vide.
# Enregistre les visages dans faces.pkl. enc et db = compare le visage actuel avec tous ceux de la base
def load(): return pickle.load(open(DB, "rb")) if os.path.exists(DB) else []
def save(e): pickle.dump(e, open(DB, "wb"))
def known(enc, db): return db and min(face_recognition.face_distance(db, enc)) <= TOL

# ── OVERLAY ──────────────────────────────────
# instructions de montrer son visage
# utilise un threading.Event pour signaler proprement au thread quand s'arrêter
# (overlay_on = False dans une fonction ne modifiait que la variable locale, pas la globale)
overlay_event = threading.Event()

def show_overlay():
    overlay_event.set()  # marque l'overlay comme actif
    cv2.namedWindow("Acces bloque", cv2.WND_PROP_FULLSCREEN)
    cv2.setWindowProperty("Acces bloque", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    while overlay_event.is_set():
        img = np.zeros((900, 1600, 3), np.uint8); img[:] = (12, 12, 18)
        cv2.putText(img, "Acces bloque",         (550, 420), cv2.FONT_HERSHEY_DUPLEX,  2.5, (80, 80, 220),  3)
        cv2.putText(img, "Souris a la camera !", (580, 500), cv2.FONT_HERSHEY_SIMPLEX, 1,   (160, 160, 255), 2)
        cv2.putText(img, datetime.now().strftime("%H:%M:%S  %A %d %B %Y"),
                    (580, 820), cv2.FONT_HERSHEY_SIMPLEX, .8, (80, 80, 110), 1)
        cv2.imshow("Acces bloque", img); cv2.waitKey(200)
    cv2.destroyWindow("Acces bloque")
    cv2.waitKey(1)  # flush nécessaire après destroyWindow

def hide_overlay():
    overlay_event.clear()  # signale au thread de s'arrêter proprement

# ── ENROLL ───────────────────────────────────
# active la cam, capture 5x mon visage et sauvegarde les données pour plus tard
def enroll():
    cap, encodings = cv2.VideoCapture(CAM), []
    print("Regarde la camera — appuie sur SPACE 5 fois pour capturer ton visage, Q pour quitter")
    while len(encodings) < 5:
        ret, frame = cap.read()
        if not ret: continue
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        locs = face_recognition.face_locations(rgb)
        [cv2.rectangle(frame, (l, t), (r, b), (0, 220, 100), 2) for t, r, b, l in locs]
        cv2.putText(frame, f"{len(encodings)}/5", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, .9, (0, 220, 100), 2)
        cv2.imshow("Enroll", frame)
        k = cv2.waitKey(1) & 0xFF
        if k == ord('q'): break
        if k == ord(' ') and len(locs) == 1:
            enc = face_recognition.face_encodings(rgb, locs)
            if enc: encodings.append(enc[0]); print(f"  {len(encodings)}/5")
    cap.release(); cv2.destroyAllWindows()
    if encodings: save(encodings); print("Enrolled!")

# ── START ────────────────────────────────────
# lance le système de surveillance, charge la db et affiche l'écran accès bloqué
def start():
    db = load()
    locked, last_auth, auth_since, last_snap = True, time.time(), None, 0
    overlay_thread = threading.Thread(target=show_overlay, daemon=True); overlay_thread.start()

# ouvre la cam, le système tourne en continu, détecte le visage et compare avec la db
    cap = cv2.VideoCapture(CAM)
    while True:
        ret, frame = cap.read()
        if not ret: continue
        rgb  = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        locs = face_recognition.face_locations(rgb)
        encs = face_recognition.face_encodings(rgb, locs)
        now  = time.time()

        auth_seen = any(known(e, db) for e in encs)
        unkn_seen = any(not known(e, db) for e in encs)

# si le visage affiché est connu ça met à jour last_auth et si le visage reste assez longtemps ça unlock le pc
# si personne n'est reconnu depuis un moment ça re-verrouille l'écran
        if auth_seen:
            last_auth = now
            auth_since = auth_since or now
            if locked and (now - auth_since) >= HOLD:
                locked = False
                hide_overlay()  # arrête proprement le thread overlay via l'Event
                print("Acces autorise")
        else:
            auth_since = None
            if not locked and (now - last_auth) >= TIMEOUT:
                locked = True
                # relancer le thread overlay seulement s'il est terminé
                if not overlay_thread.is_alive():
                    overlay_thread = threading.Thread(target=show_overlay, daemon=True)
                    overlay_thread.start()
                else:
                    overlay_event.set()
                print("Acces bloque")

# si le visage est inconnu + le système verrouillé + pas de photos récentes alors ça prend une photo et la sauvegarde
        if unkn_seen and locked and (now - last_snap) >= 1:
            last_snap = now
            Path(FOLDER).mkdir(exist_ok=True)
            path = f"{FOLDER}/intruder_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            cv2.imwrite(path, frame); print(f"Intruder saved: {path}")

        # mini preview — affiché uniquement quand l'overlay est inactif pour éviter les conflits OpenCV
        if not overlay_event.is_set():
            for (t2, r, b, l), e in zip(locs, encs):
                c = (0, 220, 100) if known(e, db) else (40, 40, 200)
                cv2.rectangle(frame, (l, t2), (r, b), c, 2)
            cv2.putText(frame, "Accès bloqué" if locked else "OK", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, .8, (40, 40, 200) if locked else (0, 220, 100), 2)
            cv2.imshow("FaceLock", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'): break

# ferme la fenêtre FaceLock et Enroll pour éviter les bugs de cam
    hide_overlay()
    cap.release(); cv2.destroyAllWindows()

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "start"
    {"enroll": enroll, "start": start}.get(cmd, lambda: print("Usage: enroll | start"))()
