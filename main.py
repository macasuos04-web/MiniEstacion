import sys, serial, serial.tools.list_ports, random, time
from threading import Thread
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget,
    QProgressBar, QDial, QTextEdit, QPushButton,
    QMessageBox, QComboBox, QLabel
)
from PySide6.QtCore import QThread, Signal, Qt

# --- Hilo que maneja la comunicación serial ---
class SerialWorker(QThread):
    data_received = Signal(str)

    def __init__(self, port, baudrate=115200):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.running = False
        self.serial_conn = None

    def run(self):
        try:
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=1)
            self.running = True
            while self.running:
                if self.serial_conn.in_waiting > 0:
                    data = self.serial_conn.readline().decode('utf-8').strip()
                    self.data_received.emit(data)
        except Exception as e:
            self.data_received.emit(f"Error: {e}")
        finally:
            if self.serial_conn and self.serial_conn.is_open:
                self.serial_conn.close()

    def send_data(self, text):
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.write((text + "\n").encode())

    def stop(self):
        self.running = False
        self.wait()


# --- Interfaz principal ---
class MiniEstacion(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🌦️ Mini Estación Meteorológica (Modo Simulación)")
        self.worker = None
        self.umbral = 50

        # --- Widgets principales ---
        self.combo_ports = QComboBox()
        self.progress = QProgressBar(); self.progress.setRange(0, 100)
        self.dial = QDial(); self.dial.setRange(0, 100)
        self.label_umbral = QLabel("Umbral: 50%")
        self.log = QTextEdit(); self.log.setReadOnly(True)
        self.btn_conectar = QPushButton("Conectar")
        self.btn_desconectar = QPushButton("Desconectar")

        # --- Layout ---
        layout = QVBoxLayout()
        for w in [self.combo_ports, self.progress, self.dial,
                  self.label_umbral, self.log, self.btn_conectar, self.btn_desconectar]:
            layout.addWidget(w)
        widget = QWidget(); widget.setLayout(layout)
        self.setCentralWidget(widget)

        # --- Conexiones ---
        self.dial.valueChanged.connect(self.actualizar_umbral)
        self.btn_conectar.clicked.connect(self.conectar)
        self.btn_desconectar.clicked.connect(self.desconectar)

        self.actualizar_puertos()

    def actualizar_puertos(self):
        self.combo_ports.clear()
        for p in serial.tools.list_ports.comports():
            self.combo_ports.addItem(p.device)

    def actualizar_umbral(self, valor):
        self.umbral = valor
        self.label_umbral.setText(f"Umbral: {valor}%")

    def conectar(self):
        port = self.combo_ports.currentText()
        if not port:
            QMessageBox.warning(self, "Error", "Selecciona un puerto COM o usa modo simulación.")
            return
        self.worker = SerialWorker(port)
        self.worker.data_received.connect(self.procesar_dato)
        self.worker.start()
        self.log.append(f"Conectado a {port}")

    
    def desconectar(self):
        if self.worker:
            try:
                self.worker.stop()
                if self.worker.serial_conn and self.worker.serial_conn.is_open:
                    self.worker.serial_conn.close()
                self.log.append("Desconectado correctamente.")
            except Exception as e:
                self.log.append(f"Error al desconectar: {e}")
            finally:
                self.worker = None
        else:
            self.log.append("No hay conexión activa.")
            
    # --- Procesar datos recibidos ---
    def procesar_dato(self, data):
        self.log.append(f"< {data}")

        # --- Lectura de humedad ---
        if data.startswith("H:"):
            try:
                valor = int(data.split(":")[1])
                self.progress.setValue(valor)

                # Comparar con el umbral
                if valor > self.umbral and not self.alerta_activa:
                    self.alerta_activa = True
                    self.progress.setStyleSheet("QProgressBar::chunk {background-color: red;}")
                    QMessageBox.warning(self, "Alerta", "¡Humedad alta detectada!")
                elif valor <= self.umbral:
                    self.alerta_activa = False
                    self.progress.setStyleSheet("")
            except:
                pass

        # --- Solicitud de estado ---
        elif data.startswith("S:REQ"):
            msg = f"ACK:UMBRAL={self.umbral}"
            if self.worker:
                self.worker.send_data(msg)
            self.log.append(f"> {msg}")


#"""
# --- Simulación sin ESP32, quitar los numerales al momento de ejecutar con el montaje del esp 32
#para que esta parte quede comentada y el programa funcione con los datos recibidos del esp32 ---
def simular_datos(hmi):
    """
    Simula lecturas del ESP32 y pulsaciones del botón.
    Genera valores de humedad y solicitudes aleatorias.

    """
    while True:
        valor = random.randint(20, 49)
        hmi.procesar_dato(f"H:{valor}")
        time.sleep(999)
        if random.random() > 0.8:  # 20% de probabilidad de "presionar el botón"
            hmi.procesar_dato("S:REQ")
#"""

# --- Programa principal ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MiniEstacion()
    win.show()

    # Activar simulación (el hilo se ejecuta en segundo plano)
    #Thread(target=simular_datos, args=(win,), daemon=True).start()

    sys.exit(app.exec())
