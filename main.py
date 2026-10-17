"""
ContextPack v1.9.0 - Generador de Contexto para IA

Punto de entrada de la aplicación

Autor: Leandro Guzmán
Empresa: Pucha Soft
"""
import logging
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from core import ConfigManager
from ui import VentanaPrincipal
from ui.theme import STYLESHEET

VERSION = "v1.9.0"


def _configurar_logging():
    """Configura el log a archivo dentro de la carpeta de configuración"""
    log_dir = Path.home() / '.contextpack'
    log_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.DEBUG,
        filename=str(log_dir / 'contextpack.log'),
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
        encoding='utf-8'
    )
    logger = logging.getLogger('contextpack')
    logger.info('Iniciando ContextPack %s', VERSION)
    return logger


def main():
    """Función principal"""
    _configurar_logging()

    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)

    config = ConfigManager()

    ventana = VentanaPrincipal(config)
    ventana.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()