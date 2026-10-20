"""
Diálogos de la aplicación
"""
import logging
from pathlib import Path
from typing import List, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QCheckBox, QTreeWidget, QTreeWidgetItem,
    QGroupBox, QSpinBox, QPlainTextEdit, QLineEdit, QHeaderView,
    QApplication
)
from PySide6.QtCore import Qt

from core import (
    FiltroArchivos, LectorGitignore, OpcionesFiltro,
    MOTIVO_CARPETA_OCULTA, MOTIVO_CARPETA_RESERVADA, MOTIVO_CARPETA_TESTS,
    MOTIVO_EXTENSION, MOTIVO_GITIGNORE, MOTIVO_LECTURA, MOTIVO_LISTA_NEGRA,
    MOTIVO_MINIFICADO, MOTIVO_TAMANO, MOTIVO_TESTS,
)

logger = logging.getLogger(__name__)


class DialogoSelectorCarpetas(QDialog):
    """Diálogo para elegir carpetas a escanear y filtros de escaneo"""

    def __init__(
        self,
        ruta: Path,
        opciones: Optional[OpcionesFiltro] = None,
        parent=None
    ):
        super().__init__(parent)
        self.ruta = ruta
        self.opciones = opciones or OpcionesFiltro()
        self.checks = {}
        self.setWindowTitle("Opciones de escaneo")
        self.setMinimumWidth(520)

        self._init_ui()

    def _init_ui(self):
        """Inicializa la interfaz"""
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Selecciona carpetas a incluir:"))

        # Listar carpetas del proyecto con los mismos filtros que el escaneo
        # (incluido el .gitignore), para no ofrecer lo que después se descarta.
        filtro = FiltroArchivos(
            gitignore=LectorGitignore(self.ruta),
            opciones=self.opciones,
        )
        carpetas = sorted([
            x for x in self.ruta.iterdir()
            if x.is_dir() and not filtro.debe_ignorar_carpeta(x.name)
        ])

        for carpeta in carpetas:
            cb = QCheckBox(f"📁 {carpeta.name}/")
            cb.setChecked(True)
            layout.addWidget(cb)
            self.checks[carpeta.name] = cb

        layout.addSpacing(8)
        layout.addWidget(self._crear_filtros())

        # Botones
        btns = QHBoxLayout()

        btn_todo = QPushButton("Seleccionar Todo")
        btn_todo.clicked.connect(self._seleccionar_todo)

        btn_ninguno = QPushButton("Deseleccionar Todo")
        btn_ninguno.clicked.connect(self._deseleccionar_todo)

        btn_ok = QPushButton("Escanear")
        btn_ok.clicked.connect(self.accept)
        btn_ok.setDefault(True)

        btns.addWidget(btn_todo)
        btns.addWidget(btn_ninguno)
        btns.addStretch()
        btns.addWidget(btn_ok)

        layout.addLayout(btns)

    def _crear_filtros(self) -> QGroupBox:
        """Crea el grupo con los filtros de escaneo"""
        grupo = QGroupBox("Filtros de escaneo")
        gl = QVBoxLayout(grupo)

        self.chk_tests = QCheckBox("Excluir tests y specs (test_*, *.spec.*, carpeta test/)")
        self.chk_tests.setChecked(self.opciones.excluir_tests)
        gl.addWidget(self.chk_tests)

        self.chk_min = QCheckBox("Excluir minificados (*.min.js, *.min.css)")
        self.chk_min.setChecked(self.opciones.excluir_minificados)
        gl.addWidget(self.chk_min)

        fila = QHBoxLayout()
        self.spin_tam = QSpinBox()
        self.spin_tam.setRange(0, 102400)
        self.spin_tam.setSingleStep(64)
        self.spin_tam.setSuffix(" KB")
        self.spin_tam.setSpecialValueText("Sin límite")
        self.spin_tam.setValue(self.opciones.tamano_max_kb)

        fila.addWidget(QLabel("Omitir archivos mayores a:"))
        fila.addWidget(self.spin_tam)
        fila.addStretch()
        gl.addLayout(fila)

        return grupo

    def _seleccionar_todo(self):
        """Selecciona todas las carpetas"""
        for cb in self.checks.values():
            cb.setChecked(True)

    def _deseleccionar_todo(self):
        """Deselecciona todas las carpetas"""
        for cb in self.checks.values():
            cb.setChecked(False)

    def obtener_seleccionadas(self) -> List[str]:
        """Retorna las carpetas seleccionadas"""
        return [nombre for nombre, cb in self.checks.items() if cb.isChecked()]

    def obtener_opciones(self) -> OpcionesFiltro:
        """Retorna los filtros de escaneo elegidos"""
        return OpcionesFiltro(
            excluir_tests=self.chk_tests.isChecked(),
            excluir_minificados=self.chk_min.isChecked(),
            tamano_max_kb=self.spin_tam.value(),
        )


class DialogoIgnorados(QDialog):
    """Detalle de los archivos y carpetas que el escaneo dejó fuera"""

    # Lo que más desconcierta va primero; lo obvio (carpetas fijas) al final
    ORDEN = [
        MOTIVO_GITIGNORE, MOTIVO_TESTS, MOTIVO_CARPETA_TESTS,
        MOTIVO_TAMANO, MOTIVO_MINIFICADO, MOTIVO_EXTENSION,
        MOTIVO_LISTA_NEGRA, MOTIVO_LECTURA,
        MOTIVO_CARPETA_RESERVADA, MOTIVO_CARPETA_OCULTA,
    ]

    PLEGADOS = {MOTIVO_CARPETA_RESERVADA, MOTIVO_CARPETA_OCULTA}

    def __init__(self, ignorados, incluidos: int = 0, parent=None):
        super().__init__(parent)
        self._entradas = list(ignorados)
        self.setWindowTitle("Qué quedó fuera del escaneo")
        self.setMinimumSize(680, 440)
        self._init_ui(incluidos)

    def _init_ui(self, incluidos: int):
        """Inicializa la interfaz"""
        layout = QVBoxLayout(self)

        archivos = sum(1 for e in self._entradas if not e.es_carpeta)
        carpetas = len(self._entradas) - archivos

        intro = QLabel(
            f"El contexto incluyó {incluidos} archivo(s). Quedaron fuera "
            f"{archivos} archivo(s) y {carpetas} carpeta(s), agrupados por motivo."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.txt_filtro = QLineEdit()
        self.txt_filtro.setPlaceholderText("Filtrar por ruta o motivo…")
        self.txt_filtro.textChanged.connect(self._aplicar_filtro)
        layout.addWidget(self.txt_filtro)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["Ruta", "Motivo"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        layout.addWidget(self.tree)

        self._poblar()

        btns = QHBoxLayout()
        btn_copiar = QPushButton("Copiar lista")
        btn_copiar.clicked.connect(self._copiar)

        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.clicked.connect(self.accept)
        btn_cerrar.setDefault(True)

        btns.addWidget(btn_copiar)
        btns.addStretch()
        btns.addWidget(btn_cerrar)
        layout.addLayout(btns)

    def _clave_orden(self, motivo: str):
        """Ordena los grupos por relevancia y deja los desconocidos al final"""
        if motivo in self.ORDEN:
            return (self.ORDEN.index(motivo), '')
        return (len(self.ORDEN), motivo)

    def _poblar(self):
        """Arma un grupo por motivo con sus rutas"""
        grupos = {}
        for entrada in self._entradas:
            grupos.setdefault(entrada.motivo, []).append(entrada)

        for motivo in sorted(grupos, key=self._clave_orden):
            entradas = sorted(grupos[motivo], key=lambda e: e.ruta_relativa.lower())

            grupo = QTreeWidgetItem(self.tree, [f"{motivo} ({len(entradas)})", ""])
            grupo.setFirstColumnSpanned(True)
            fuente = grupo.font(0)
            fuente.setBold(True)
            grupo.setFont(0, fuente)

            for entrada in entradas:
                ruta = entrada.ruta_relativa
                if entrada.es_carpeta:
                    ruta += "/"
                hijo = QTreeWidgetItem(grupo, [ruta, motivo])
                hijo.setToolTip(0, ruta)

            grupo.setExpanded(motivo not in self.PLEGADOS)

    def _aplicar_filtro(self, texto: str):
        """Oculta las filas que no coinciden con el texto buscado"""
        buscado = texto.strip().lower()

        for i in range(self.tree.topLevelItemCount()):
            grupo = self.tree.topLevelItem(i)
            visibles = 0
            for j in range(grupo.childCount()):
                hijo = grupo.child(j)
                coincide = (
                    not buscado
                    or buscado in hijo.text(0).lower()
                    or buscado in hijo.text(1).lower()
                )
                hijo.setHidden(not coincide)
                visibles += int(coincide)

            grupo.setHidden(visibles == 0)
            if buscado and visibles:
                grupo.setExpanded(True)

    def _copiar(self):
        """Copia el detalle como texto plano, agrupado por motivo"""
        lineas = []
        for i in range(self.tree.topLevelItemCount()):
            grupo = self.tree.topLevelItem(i)
            if grupo.isHidden():
                continue
            lineas.append(grupo.text(0))
            for j in range(grupo.childCount()):
                hijo = grupo.child(j)
                if not hijo.isHidden():
                    lineas.append(f"  {hijo.text(0)}")
            lineas.append("")

        QApplication.clipboard().setText("\n".join(lineas).rstrip())


class DialogoPlantilla(QDialog):
    """Diálogo para editar el texto de la plantilla personalizada"""

    def __init__(self, texto: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Plantilla personalizada")
        self.setMinimumSize(600, 420)
        self._init_ui(texto)

    def _init_ui(self, texto: str):
        """Inicializa la interfaz"""
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Instrucciones que se anteponen al contexto al copiar o exportar:"
        ))

        self.txt = QPlainTextEdit(texto)
        self.txt.setPlaceholderText(
            "Ej: Actuá como desarrollador senior y explicame la arquitectura..."
        )
        layout.addWidget(self.txt)

        btns = QHBoxLayout()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)

        btn_ok = QPushButton("Guardar")
        btn_ok.clicked.connect(self.accept)
        btn_ok.setDefault(True)

        btns.addStretch()
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_ok)
        layout.addLayout(btns)

    def texto(self) -> str:
        """Texto de la plantilla editada"""
        return self.txt.toPlainText()


class DialogoAnalizarDep(QDialog):
    """Diálogo para análisis de dependencias"""
    
    def __init__(
        self,
        ruta: Path,
        opciones: Optional[OpcionesFiltro] = None,
        parent=None
    ):
        super().__init__(parent)
        self.ruta = ruta
        self.opciones = opciones or OpcionesFiltro()
        self.archivo = None
        self.setWindowTitle("Análisis de Dependencias")
        self.setMinimumSize(600, 400)
        
        self._init_ui()
    
    def _init_ui(self):
        """Inicializa la interfaz"""
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("🔍 Selecciona archivo para analizar sus dependencias:"))
        
        # Árbol de archivos
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Archivos")
        self.tree.itemDoubleClicked.connect(lambda *_: self._analizar())
        layout.addWidget(self.tree)
        
        self._poblar_arbol()
        
        # Botones
        btns = QHBoxLayout()
        btn_ok = QPushButton("Analizar")
        btn_ok.clicked.connect(self._analizar)
        btn_ok.setDefault(True)
        
        btns.addStretch()
        btns.addWidget(btn_ok)
        layout.addLayout(btns)
    
    def _poblar_arbol(self):
        """Puebla el árbol con los archivos que el escaneo sí incluiría"""
        filtro = FiltroArchivos(
            gitignore=LectorGitignore(self.ruta),
            opciones=self.opciones,
        )
        
        def agregar_items(parent, directorio):
            try:
                items = sorted(
                    directorio.iterdir(),
                    key=lambda x: (not x.is_dir(), x.name)
                )
            except Exception:
                logger.debug('Error iterando %s', directorio, exc_info=True)
                return
            
            for item in items:
                try:
                    rel = str(item.relative_to(self.ruta))
                except ValueError:
                    rel = item.name

                if item.is_dir():
                    if not filtro.debe_ignorar_carpeta(item.name, rel):
                        tree_item = QTreeWidgetItem(parent, [f"📁 {item.name}"])
                        tree_item.setData(0, Qt.UserRole, str(item))
                        agregar_items(tree_item, item)
                elif filtro.debe_incluir_archivo(item, rel):
                    tree_item = QTreeWidgetItem(parent, [item.name])
                    tree_item.setData(0, Qt.UserRole, str(item))
        
        agregar_items(self.tree, self.ruta)
        self.tree.expandAll()
    
    def _analizar(self):
        """Analiza el archivo seleccionado"""
        item = self.tree.currentItem()
        if not item:
            return
        
        ruta = Path(item.data(0, Qt.UserRole))
        if ruta.is_file():
            self.archivo = ruta
            self.accept()