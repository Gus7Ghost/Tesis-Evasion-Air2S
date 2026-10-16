import os
import ctypes

# Inyectar la variable directamente en el C-Runtime de Windows (msvcrt) para que la DLL de OpenCV/FFMPEG la lea
opt = "OPENCV_FFMPEG_CAPTURE_OPTIONS=protocol_whitelist;file,rtp,udp"
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "protocol_whitelist;file,rtp,udp"
try:
    ctypes.cdll.msvcrt._putenv(opt.encode("ascii"))
except Exception as e:
    print(f"[Aviso msvcrt] {e}")

import cv2
import time

def test_stream():
    print("=" * 65)
    print("  TEST DE RECEPCIÓN DE VIDEO ROSETTADRONE (UDP Puerto 5600)")
    print("=" * 65)

    sdp_path = "rosetta.sdp"
    if not os.path.exists(sdp_path):
        with open(sdp_path, "w") as f:
            f.write("c=IN IP4 0.0.0.0\nm=video 5600 RTP/AVP 96\na=rtpmap:96 H264/90000\n")

    print(f"Abriendo descriptor SDP ({sdp_path}) escuchando en UDP :5600...")
    cap = cv2.VideoCapture(sdp_path, cv2.CAP_FFMPEG)

    if not cap.isOpened():
        print("\n[ERROR] No se pudo abrir el descriptor SDP.")
        return

    print("\n[ÉXITO TOTAL] Socket UDP 5600 y FFMPEG vinculados correctamente!")
    print("Esperando frames de video del DJI Air 2S... (Presiona 'q' para salir)\n")

    frame_count = 0
    start_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            # Esperando el primer frame
            if frame_count == 0 and time.time() - start_time > 10:
                print("[Esperando señal... Asegúrate que en la tablet se vea la cámara del dron]")
                start_time = time.time()
            continue

        frame_count += 1
        cv2.putText(frame, f"DJI Air 2S - Frames: {frame_count}", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
        cv2.imshow("Video en Vivo - DJI Air 2S", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    print("[INFO] Test de video finalizado con éxito.")

if __name__ == "__main__":
    test_stream()
