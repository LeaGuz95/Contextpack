"""
Plantillas de instrucciones para anteponer al contexto.

Cada plantilla es el texto que se manda antes del proyecto: lo que le pedís
a la IA que haga con ese código. Van cortas y con guardas contra inventar,
que es el motivo por el que existe la aplicación.
"""

SIN_PLANTILLA = "Sin plantilla"
PERSONALIZADA = "Personalizada"

PLANTILLAS = {
    "Explicar el proyecto": (
        "Actuá como desarrollador senior y explicame este proyecto.\n"
        "1. Qué hace y para quién.\n"
        "2. La arquitectura: módulos, responsabilidades y cómo se comunican.\n"
        "3. El flujo principal, paso a paso, desde el punto de entrada.\n"
        "4. Las decisiones de diseño que veas y qué trade-offs implican.\n\n"
        "Basa todo en el contexto que te paso. Si algo no está, decí que no "
        "está en vez de suponerlo."
    ),
    "Refactor y mejoras": (
        "Actuá como revisor de código senior.\n"
        "Detectá: duplicación, funciones demasiado largas, acoplamiento, "
        "manejo de errores faltante y deuda técnica.\n"
        "Para cada problema: archivo, por qué es un problema y el cambio "
        "concreto que proponés, con el código.\n"
        "Ordená por impacto y no reescribas lo que ya está bien."
    ),
    "Buscar bugs": (
        "Buscá bugs reales en el código que sigue.\n"
        "Para cada uno: archivo, ubicación aproximada, qué condición lo "
        "dispara, qué se rompe y cómo arreglarlo.\n"
        "No reportes cuestiones de estilo ni de formato.\n"
        "Si no encontrás bugs, decilo y explicá qué revisaste."
    ),
    "Escribir tests": (
        "Escribí tests para el código que sigue.\n"
        "Cubrí el camino feliz y los casos borde: entradas vacías, None, "
        "límites y errores esperados.\n"
        "Indicá el framework que asumís y cómo correrlos.\n"
        "No inventes funciones que no existan en el contexto."
    ),
    "Documentar": (
        "Generá la documentación de este proyecto en Markdown:\n"
        "1. Qué es y cómo se instala.\n"
        "2. Cómo se usa, con un ejemplo concreto.\n"
        "3. Los módulos principales y qué hace cada uno.\n"
        "4. Configuración y variables de entorno, si hay.\n\n"
        "Escribí para alguien que abre el repositorio por primera vez."
    ),
}


def texto_plantilla(nombre: str, personalizada: str = "") -> str:
    """Resuelve el texto de una plantilla por su nombre"""
    if nombre == SIN_PLANTILLA:
        return ""
    if nombre == PERSONALIZADA:
        return personalizada
    return PLANTILLAS.get(nombre, '')
