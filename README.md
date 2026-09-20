# Agente Inteligente — Análisis Estructural de Redes de Proyectos

**Investigación de Operaciones — Grupo 6**
Tema: *Técnicas de Planeación de Redes — Análisis de la Estructura*

## Descripción

Sistema que integra un **modelo matemático** de redes de proyectos (grafo
dirigido acíclico), su **implementación computacional** en Python y un
**agente de IA híbrido** (reglas + LLM) que interpreta los resultados.

El caso de aplicación es la **planeación estructural de un proyecto de
desarrollo de software** (proyecto TI). El sistema:

- Construye el DAG de actividades a partir de sus relaciones de precedencia.
- Valida propiedades estructurales: aciclicidad, conectividad débil,
  existencia de nodo fuente y nodo sumidero.
- Calcula el ordenamiento topológico.
- Enumera los caminos del nodo fuente al sumidero.
- Identifica nodos estructuralmente críticos (centralidad por paso de caminos).
- Detecta puntos de articulación (cuellos de botella estructurales).
- Clasifica las actividades: iniciales, finales, intermedias y paralelas.
- Genera un reporte interpretado por el agente de IA.

> **Alcance:** el enfoque es **exclusivamente estructural**. No se tratan
> duraciones, holguras temporales, costos ni asignación de recursos.

### Modelo matemático

Sea `G = (V, E)` un grafo dirigido acíclico donde `V` son las actividades y
`E ⊆ V × V` las relaciones de precedencia. El análisis busca:

```
V* = argmax_{v ∈ V} σ(v)
```

donde `σ(v)` es el número de caminos fuente→sumidero que pasan por `v`.
Los nodos de `V*` son los **estructuralmente críticos**.

### Agente de IA híbrido

1. **Capa determinista** (reglas + plantillas): detecta patrones en los
   resultados del analizador y genera un reporte estructurado.
2. **Capa LLM** (Claude API): redacta la explicación en lenguaje natural y
   responde preguntas abiertas sobre la red.

Si no hay clave API o falla la conexión, el agente opera en **modo fallback**
usando solo la capa determinista. El LLM nunca realiza el análisis matemático:
solo interpreta los resultados del modelo.

## Requisitos

- Python 3.10 o superior
- Dependencias en `requirements.txt` (`networkx`, `matplotlib`, `anthropic`,
  `python-dotenv`, `pytest`)

## Instalación

```bash
# 1. Clonar el repositorio y entrar a la carpeta
cd proyecto_redes_estructura

# 2. Crear y activar un entorno virtual
python -m venv .venv
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\activate         # Windows

# 3. Instalar el proyecto y sus dependencias (modo editable)
pip install -e ".[dev]"

# 4. Configurar la clave API (opcional — sin ella se usa el modo fallback)
cp .env.example .env
# editar .env y reemplazar el valor de ANTHROPIC_API_KEY
```

## Uso

```bash
pna
```

Equivalente: `python -m project_network_analyzer`.

Esto:

1. Carga el caso de prueba desde `data/proyecto_software.json`.
2. Construye y valida la red.
3. Ejecuta el análisis estructural completo.
4. Genera la visualización del grafo en `outputs/grafo_red.png`.
5. Genera el reporte interpretado en `outputs/reporte.txt`.

Opciones:

```bash
pna --datos data/otra_red.json     # analizar otra red
pna --pregunta "¿Cuál es el nodo más crítico?"
pna --modelo claude-sonnet-5       # cambiar el modelo de la capa LLM
```

Para ejecutar las pruebas (no hacen falta ni clave API ni instalación):

```bash
pytest
```

## Estructura del proyecto

```
proyecto_redes_estructura/
├── CLAUDE.md                    # Contexto y guía del proyecto
├── README.md                    # Este archivo
├── pyproject.toml               # Empaquetado, dependencias y pytest
├── requirements.txt             # Atajo que apunta a pyproject.toml
├── .env.example                 # Plantilla de la clave API
├── .gitignore
├── data/
│   └── proyecto_software.json   # Caso de prueba: app web (15 actividades)
├── src/project_network_analyzer/
│   ├── domain/
│   │   ├── errors.py            # NetworkStructureError
│   │   ├── network.py           # Clase Network y validaciones estructurales
│   │   └── analysis.py          # Caminos, centralidad, articulación
│   ├── services/
│   │   └── report.py            # Capa de reglas: reporte determinista
│   ├── agent/
│   │   ├── llm_agent.py         # Capa LLM (Claude API) con fallback
│   │   └── prompts.py           # Prompts de la capa LLM
│   ├── infrastructure/
│   │   ├── loader.py            # Lectura del JSON desde disco
│   │   └── rendering.py         # Grafo con networkx + matplotlib
│   ├── config.py                # Configuración de la capa LLM
│   └── cli.py                   # Orquestador
├── tests/
│   ├── domain/                  # Pruebas del modelo y del analizador
│   ├── services/                # Pruebas de la capa de reglas
│   ├── agent/                   # Pruebas del agente (modo fallback)
│   └── infrastructure/          # Pruebas del loader
└── outputs/                     # Salidas generadas (grafo y reporte)
```

## Caso de prueba

`data/proyecto_software.json` modela el desarrollo de una aplicación web de
gestión de tareas con 15 actividades (A–O), desde el levantamiento de
requisitos hasta el cierre del proyecto. Incluye ramas paralelas (diseño de
arquitectura vs. UI/UX, integración vs. pruebas unitarias) que hacen
interesante el análisis estructural.

## Equipo

Grupo 6 — Investigación de Operaciones.
