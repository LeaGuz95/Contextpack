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
    
    @staticmethod
    def _valores_por_defecto() -> Dict:
        """Valores por defecto de la configuración"""
        return {
            'ultima_carpeta': str(Path.home()),
            'proyectos_recientes': [],
            'mostrar_advertencia_seguridad': True,
            'modelo_objetivo': 'Personalizado',
            'perfiles': {},
            'plantilla_nombre': 'Sin plantilla',
            'plantilla_personalizada': '',
            'excluir_tests': False,
            'excluir_minificados': True,
            'tamano_max_kb': 1024,
            'quitar_comentarios': False,
            'quitar_lineas_vacias': False,
            'ventana_ancho': 1200,
            'ventana_alto': 850
        }

    def _cargar_config(self) -> Dict:
        """
        Carga la configuración desde disco.

        Las claves que falten —por venir de una versión anterior— se completan
        con los valores por defecto, así el archivo siempre termina teniendo
        todas las claves documentadas.
        """
        defectos = self._valores_por_defecto()

        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return {**defectos, **json.load(f)}
            except Exception:
                logger.warning('No se pudo leer el config, se usan valores por defecto', exc_info=True)

        return defectos
    
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

    def guardar_perfil(self, raiz: str, perfil: Dict):
        """Guarda el perfil de un proyecto (máximo 20 proyectos recordados)"""
        perfiles = self.config.setdefault('perfiles', {})
        perfiles.pop(raiz, None)
        perfiles[raiz] = perfil

        while len(perfiles) > 20:
            perfiles.pop(next(iter(perfiles)))

        self.guardar()

    def obtener_perfil(self, raiz: str) -> Dict:
        """
        Devuelve el perfil guardado de un proyecto.

        Si no hay perfil, cae a las selecciones de la versión 1.6.0, que solo
        recordaban qué archivos quedaban fuera.
        """
        perfil = self.config.get('perfiles', {}).get(raiz)
        if perfil:
            return perfil

        antiguos = self.config.get('selecciones', {}).get(raiz)
        if antiguos:
            return {'seleccion': antiguos}

        return {}