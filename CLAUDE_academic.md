# Proyecto: Agente Inteligente — Análisis Estructural de Redes de Proyectos

## Contexto del proyecto

Proyecto universitario final para la asignatura de **Investigación de Operaciones**.
**Grupo 6 — Tema: Técnicas de Planeación de Redes, Análisis de la Estructura.**

El sistema integra:
1. Un **modelo matemático** de redes de proyectos (grafo dirigido acíclico).
2. Una **implementación computacional** en Python.
3. Un **agente de IA híbrido** (reglas + LLM) que interpreta los resultados.

**Caso de aplicación elegido:** planeación estructural de un proyecto de desarrollo de software (proyecto TI).

## Alcance específico del Grupo 6

A diferencia de otros grupos (que tratan tiempos, costos o recursos), nuestro enfoque
es exclusivamente el **análisis estructural** de la red:

- Construcción del DAG de actividades.
- Validación de propiedades estructurales (aciclicidad, conectividad, fuente/sumidero).
- Ordenamiento topológico.
- Enumeración de caminos del nodo fuente al sumidero.
- Identificación de nodos críticos estructurales (centralidad por paso de caminos).
- Detección de puntos de articulación (cuellos de botella estructurales).
- Clasificación de actividades: iniciales, finales, intermedias, paralelas.

**NO entramos en:** duración de actividades, holguras temporales, costos, ni asignación
de recursos. Eso pertenece a los grupos 7, 8, 9 y 10.

## Modelo matemático

Sea G = (V, E) un grafo dirigido acíclico donde:
- V = conjunto de actividades del proyecto.
- E ⊆ V × V = relaciones de precedencia.

**Restricciones:**
1. Aciclicidad: no existe ciclo dirigido en G.
2. Conectividad débil.
3. Existencia de al menos un nodo fuente (grado de entrada = 0).
4. Existencia de al menos un nodo sumidero (grado de salida = 0).

**Función objetivo del análisis:**
Identificar V* = argmax_{v ∈ V} σ(v), donde σ(v) es el número de caminos
fuente→sumidero que pasan por v. Estos son los nodos estructuralmente críticos.

## Arquitectura del código

```
proyecto_redes_estructura/
├── CLAUDE.md
├── README.md
├── requirements.txt
├── .env                         # ANTHROPIC_API_KEY=...
├── data/
│   └── proyecto_software.json
├── src/
│   ├── modelo.py                # Clase Red, validaciones estructurales
│   ├── analizador.py            # Análisis: caminos, centralidad, articulación
│   ├── visualizador.py          # Grafo con networkx + matplotlib
│   ├── agente_ia.py             # Agente híbrido (reglas + Claude API)
│   └── main.py                  # Orquestador
├── tests/
│   └── test_modelo.py
└── outputs/
    ├── grafo_red.png
    └── reporte.txt
```

## Stack técnico

- **Lenguaje:** Python 3.10+
- **IDE:** PyCharm
- **Librerías principales:**
  - `networkx` — grafos y algoritmos
  - `matplotlib` — visualización
  - `anthropic` — cliente del API de Claude
  - `python-dotenv` — manejo de la clave API
  - `pytest` — pruebas

## Diseño del Agente de IA (híbrido)

El agente tiene dos componentes:

**1. Capa determinista (reglas + plantillas):**
Toma los resultados del analizador y detecta patrones:
- "Hay N caminos críticos estructurales → ..."
- "El nodo X es punto de articulación → ..."
- "Existen K actividades paralelas en la fase inicial → ..."
Genera un reporte estructurado en texto.

**2. Capa LLM (Claude API):**
Recibe el reporte estructurado como contexto y:
- Redacta una explicación en lenguaje natural.
- Responde preguntas abiertas del usuario sobre la red.
- Sugiere mejoras en la estructura del proyecto.

**Modo fallback:** si no hay clave API o falla la conexión, el agente usa solo la
capa determinista. Nunca queda inoperante.

**Importante:** el LLM NUNCA hace el análisis matemático, solo interpreta los
resultados del modelo. Esto cumple la condición del proyecto: "La IA no reemplaza
el modelo".

## Convenciones de código

- Docstrings en español (es proyecto universitario en español).
- Nombres de variables en español también para claridad académica.
- Cada función del análisis debe ser determinista y testeable.
- Comentar las funciones del modelo matemático indicando qué fórmula implementan.

## Estado actual

[Actualizar a medida que avanza]
- [x] Estructura de carpetas creada
- [x] requirements.txt con dependencias
- [x] Caso de prueba (data/proyecto_software.json) — app web, 15 actividades (A–O)
- [x] modelo.py — clase Red con validaciones (DAG, aciclicidad, conectividad, fuente/sumidero) — verificado con el caso de prueba
- [x] analizador.py — orden topológico, caminos f→s, centralidad σ(v), V*, cuellos de botella, puntos de articulación, clasificación y generaciones — verificado (DP vs. enumeración coinciden)
- [x] visualizador.py — grafo por generaciones (networkx + matplotlib, backend Agg) con roles estructurales coloreados → outputs/grafo_red.png — verificado
- [x] agente_ia.py — agente híbrido: capa determinista (reglas/plantillas) + capa LLM (Claude Haiku 4.5, configurable) con modo fallback — verificado en ambos modos
- [x] main.py — orquestador (JSON→validación→análisis→PNG→agente→reporte.txt), CLI con --datos/--pregunta/--modelo — verificado de extremo a extremo
- [x] tests básicos — pytest: test_modelo.py + test_analizador.py + test_agente.py (41 tests, fallback sin API) — todos pasan

**Proyecto completo: los 9 ítems del checklist están terminados y verificados.**

## Notas para Claude Code

- El proyecto debe poder ejecutarse con: `python src/main.py`
- El reporte y el grafo se guardan en `outputs/`
- La clave API va en `.env` (nunca hardcoded).
- Si el usuario pide cambios en el modelo matemático, recordar que el alcance
  del Grupo 6 es ESTRUCTURAL, no temporal ni de costos.
