"""
Gestión de configuración persistente
"""
import json
import logging
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)


class ConfigManager:
    """Maneja la configuración persistente de la aplicación"""
    
    def __init__(self):
        self.config_path = Path.home() / '.contextpack' / 'config.json'
        self.config = self._cargar_config()
    
    def _cargar_config(self) -> Dict:
        """Carga la configuración desde disco"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                logger.warning('No se pudo leer el config, se usan valores por defecto', exc_info=True)
        
        return {
            'ultima_carpeta': str(Path.home()),
            'proyectos_recientes': [],
            'mostrar_advertencia_seguridad': True,
            'ventana_ancho': 1200,
            'ventana_alto': 850
        }
    
    def guardar(self):
        """Guarda la configuración en disco"""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception:
            logger.warning('No se pudo guardar el config', exc_info=True)
    
    def agregar_proyecto_reciente(self, ruta: str):
        """Agrega un proyecto a la lista de recientes"""
        recientes = self.config.get('proyectos_recientes', [])
        if ruta in recientes:
            recientes.remove(ruta)
        recientes.insert(0, ruta)
        self.config['proyectos_recientes'] = recientes[:10]
        self.guardar()