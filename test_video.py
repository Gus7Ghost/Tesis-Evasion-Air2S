import cv2
import yaml
import os
import sys

def test_rtsp():
    config_path = "config.yaml"
    if not os.path.exists(config_path):
        print(f"[Error] No se encontró {config_path}")
        return

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    rtsp_uri = config.get("network", {}).get("video_stream_uri", "")
    print("=" * 60)
    print("  TEST RÁPIDO DE CÁMARA RTSP (Air 2S / RosettaDrone)")
    print("=" * 60)
    print(f"Probando conexión a: {rtsp_uri}")
    print("Presiona 'q' en la ventana para salir.\n")

    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp|fflags;nobuffer|flags;low_delay"
    cap = cv2.VideoCapture(rtsp_uri, cv2.CAP_FFMPEG)

    if not cap.isOpened():
        print(f"[FALLO] No se pudo conectar al flujo RTSP.")
        print("Causas posibles:")
        print(" 1. La IP de la tablet cambió (Verifícala en la pantalla de la tablet).")
        print(" 2. En RosettaDrone no está encendido el switch 'Enable Video Streaming'.")
        print(" 3. El firewall de Windows está bloqueando el puerto 8554.")
        return

    print("[ÉXITO] Conexión RTSP establecida. Esperando frames...")
    frame_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[Advertencia] Se perdió el frame o hubo timeout...")
            continue

        frame_count += 1
        cv2.putText(frame, f"Air2S Stream OK - Frames: {frame_count}", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.imshow("Test Camara RosettaDrone", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    print("[INFO] Test de video finalizado.")

if __name__ == "__main__":
    test_rtsp()
