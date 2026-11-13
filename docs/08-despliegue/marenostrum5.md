# Pruebas en MareNostrum 5 (BSC)

*Última actualización: 2026-11-11 (Python propio con uv y uso dentro de `salloc`)*

Esta guía sirve para hacer las pruebas de **consola** (y las pruebas automáticas y en vivo) en MareNostrum 5 (MN5), el supercomputador del Barcelona Supercomputing Center (BSC), en lugar del PC de pruebas. Complementa la [guía de instalación](instalacion.md) y la guía operativa de MN5 que entrega el BSC.

> **Estado:** la consola funcionó en MN5 el 2026-11-08 (H100, ~57 tokens/s en el análisis después del primer turno). El cambio a un Python propio (2026-11-11) se probó con dobles. **TODO:** confirmarlo en MN5.

## Qué cambia respecto al PC de pruebas
| | PC de pruebas | MN5 |
|---|---|---|
| Dónde se escribe | En el mismo PC | En el **nodo de acceso** `glogin4`, compartido por muchos usuarios: solo se preparan archivos y se descarga |
| Dónde corren los modelos | En la GPU del PC | En un **nodo con GPU H100** (partición `acc`) que se pide a SLURM por un tiempo limitado (2 h en `acc_debug`) |
| Internet | Sí | Solo en `glogin4`. Los nodos de GPU **no tienen internet**: todo se descarga antes |
| Python | El del sistema | Un **CPython 3.12 propio** ("standalone", instalado con `uv` en GPFS). No se usan los módulos de Python de MN5: los nodos GPP (como `glogin4`) y ACC (GPU) tienen módulos distintos, y el Python de ACC no carga `sqlite3` con la librería del sistema (`undefined symbol: sqlite3_deserialize`, 2026-11-11) |
| Ollama | Servicio del sistema (`sudo`) | Programa en la carpeta del proyecto (no hay `sudo`), con los modelos en GPFS (`OLLAMA_MODELS`) |
| Puerto de Ollama | 11434 | Uno al azar en `127.0.0.1` en cada sesión, porque los nodos son compartidos. Los scripts lo pasan en `OLLAMA_BASE_URL`, que tiene prioridad sobre `.env` |

Las H100 de MN5 tienen 64 GB de memoria, así que los modelos de ADR 0011 caben en la GPU. La configuración de `.env.example` (respuesta con `qwen3-cpu`) se deja igual que en el PC: cambiarla es decisión del equipo (ADR 0011). En el `.env` de MN5 sí conviene `OLLAMA_EMBED_NUM_GPU=auto`: con `0` el embedder corre en la CPU y construir el índice tarda decenas de minutos. Ese `.env` no se versiona.

El primer turno de cada sesión es lento (en la prueba, el análisis tardó 33 s): la GPU se prepara en la primera llamada. Desde el segundo turno, el análisis tarda unos 2 s.

## Qué no se hace en MN5
- **WhatsApp ni ngrok:** no se conocen las reglas de red del BSC. La guía del BSC pide no abrir puertos de un servidor de LLM sin su revisión.
- **Interfaz web (`run_web.py`):** pendiente. Para verla desde el PC haría falta un túnel SSH hasta el nodo con GPU, y la guía del BSC pide no usar redirecciones de puertos sin autorización. **TODO:** preguntar a soporte del BSC si se permite un túnel SSH a un nodo `acc` propio para un servicio que escucha solo en `127.0.0.1`.
- **Base de datos ni `.env` del PC de pruebas:** la carpeta del proyecto es compartida y los servidores están en España. `preparar.sh` crea un `.env` nuevo, sin los secretos de WhatsApp, y la base `data/cardio_materno.db` se crea vacía. Solo se usan datos sintéticos (ver [protección de datos](../07-gobernanza/proteccion-datos.md)).
- **Cuentas compartidas:** según la guía del BSC, cada persona entra con su propia identidad del BSC.

## Organización en GPFS
```
/gpfs/projects/bsc08/bsc001997/cardio_materno/   ← MN5_WORK (la carpeta que contiene el repositorio)
├── chatbot-cardio-materno/   repositorio (git clone), con su .venv, .env y data/
├── uv/                       uv (un solo binario) y su caché
├── python/                   CPython 3.12 propio (lo instala uv)
├── ollama/bin, ollama/lib    Ollama (sin instalar en el sistema)
├── ollama/models             modelos (~25 GB)
├── logs/                     logs de Ollama por job (ollama-<job>.log)
└── mn5.conf                  configuración local de los scripts (no se versiona)
```

## 1. Comprobaciones (una vez, en `glogin4`)
Conéctate (VPN del BSC + VS Code Remote-SSH, como indica la guía del BSC) y abre una terminal:
```bash
bsc_queues            # debe aparecer acc_debug
bsc_project list      # cuenta bsc08
curl -sI https://github.com | head -1   # internet en glogin4: "HTTP/... 200" o "301"
```
Revisa también el espacio libre del proyecto (`bsc_quota`): los modelos ocupan unos 25 GB.

## 2. Preparar (una vez, en `glogin4`)
```bash
mkdir -p /gpfs/projects/bsc08/bsc001997/cardio_materno
cd /gpfs/projects/bsc08/bsc001997/cardio_materno
git clone https://github.com/NicolasCastilloGaleano/chatbot-cardio-materno.git
cd chatbot-cardio-materno
bash scripts/mn5/preparar.sh
```
No hace falta ningún `module load`: si tienes módulos de Python cargados en la terminal, los scripts quitan `PYTHONPATH` y `PYTHONHOME`.

`preparar.sh` hace cuatro pasos y se puede repetir, porque salta lo que ya está hecho:
1. Descarga `uv` (un solo binario) en `uv/`, instala con él CPython 3.12 en `python/` y crea `.venv` con ese Python. Si encuentra un `.venv` hecho con otro Python (por ejemplo, el de un módulo), lo vuelve a crear, porque es derivado. Instala `requirements.txt` y `requirements-dev.txt` y verifica que `.venv` cargue `sqlite3`.
2. Descarga Ollama para Linux y lo descomprime en `ollama/`.
3. Arranca un Ollama temporal sin GPU, descarga `mistral-small3.1:24b`, `qwen3:8b` y `qwen3-embedding:8b`, y crea `qwen3-cpu` con [qwen3-cpu.Modelfile](qwen3-cpu.Modelfile). Al terminar, lo detiene.
4. Crea `.env` desde `.env.example`, si no existe.

`uv` es una herramienta de operación en MN5, como Ollama: no es una dependencia del proyecto ni cambia `requirements.txt`.

**Sin internet en `glogin4`:** descarga en tu PC `uv-x86_64-unknown-linux-gnu.tar.gz` (de las versiones de `astral-sh/uv` en GitHub) y `ollama-linux-amd64.tgz`, súbelos por `transfer1.bsc.es` (sección 5 de la guía del BSC) y ejecuta `MN5_UV_ARCHIVE=/ruta/uv.tar.gz MN5_OLLAMA_ARCHIVE=/ruta/ollama.tgz bash scripts/mn5/preparar.sh`. Instalar el Python también necesita internet. Los modelos se suben del mismo modo, copiando `blobs/` y `manifests/` a `ollama/models`.

## 3. Probar con una GPU (cada vez, desde `glogin4`)
```bash
cd /gpfs/projects/bsc08/bsc001997/cardio_materno/chatbot-cardio-materno
bash scripts/mn5/pedir_gpu.sh                  # consola del chat
```
`pedir_gpu.sh` pide 1 H100 con `srun --pty` (cuenta `bsc08`, cola `acc_debug`, 20 CPU, máximo 2 h; se cambian en `mn5.conf`) y ejecuta `sesion_gpu.sh` en ese nodo. Puede tardar si la cola está llena; Ctrl+C cancela la solicitud. `sesion_gpu.sh` arranca Ollama, muestra la GPU, ejecuta las acciones pedidas y, al terminar, detiene Ollama. La GPU se libera sola.

### Varias sesiones con una sola espera en la cola (`salloc`)
`salloc` también espera en la cola, pero una sola vez: la GPU queda reservada hasta 2 h y se puede entrar y salir sin volver a esperar.
```bash
salloc -A bsc08 -q acc_debug -p acc -N 1 --ntasks=1 --gres=gpu:1 --cpus-per-task=20 -t 02:00:00
bash scripts/mn5/pedir_gpu.sh            # entra en la reserva; repetirlo no vuelve a la cola
scancel $SLURM_JOB_ID                    # al terminar: libera la GPU
```
Dentro de la reserva, `pedir_gpu.sh` la detecta y usa `srun --jobid`. Mientras la reserva está activa, no escribas `exit` en esa terminal (guía del BSC). Si no la liberas con `scancel`, la GPU queda ocupada hasta que se acaba el tiempo, y ese tiempo se descuenta de las horas del proyecto.

### Acciones
Se pueden encadenar acciones en una misma sesión:
| Acción | Qué hace |
|---|---|
| `consola` (por defecto) | `run_console.py`. Si no existe `data/kb_index`, primero construye el índice |
| `indice` | `run_build_kb_index.py` (cuando cambia `knowledge/kb/entries.jsonl` o el modelo de embeddings) |
| `pruebas` | `pytest` sin Ollama |
| `live` | `pytest -m live -s` |
| `shell` | Terminal en el nodo con Ollama ya arrancado (`OLLAMA_BASE_URL` definida). `exit` termina la sesión |

Ejemplo: `bash scripts/mn5/pedir_gpu.sh pruebas live consola`.

Los guiones de prueba son los mismos de la [guía de instalación](instalacion.md#guiones-de-prueba).

## Actualizar el código
En `glogin4`: `git pull` y, si cambiaron las dependencias, `bash scripts/mn5/preparar.sh`.

## Problemas frecuentes
| Mensaje | Solución |
|---|---|
| `ImportError: … _sqlite3 … undefined symbol: sqlite3_deserialize` | El `.venv` se hizo con un módulo de Python de MN5. Ejecuta `bash scripts/mn5/preparar.sh` en `glogin4`: lo rehace con el Python propio |
| `.venv falta o usa otro Python…` | Lo mismo: `bash scripts/mn5/preparar.sh` en `glogin4` |
| `No se pudo descargar uv` u `Ollama` | Sin internet en `glogin4`: sube los paquetes por `transfer1` y usa `MN5_UV_ARCHIVE` / `MN5_OLLAMA_ARCHIVE` |
| `Ejecútalo en glogin4, fuera de una asignación…` | `preparar.sh` descarga, así que va fuera de `salloc`: libera la reserva (`scancel`) o usa otra terminal |
| `Este script corre en el nodo con GPU…` | Usa `pedir_gpu.sh`, no `sesion_gpu.sh` directamente |
| `Ollama no arrancó…` | Revisa `logs/ollama-<job>.log` (por ejemplo, librerías de CUDA o un puerto ocupado) |
| `srun: error: … Invalid qos` o `Invalid account` | Revisa `bsc_queues` y `bsc_project list`, y ajusta `MN5_QOS` en `mn5.conf` |
| La solicitud queda esperando mucho tiempo | La cola está llena: `squeue --me` muestra el estado; Ctrl+C la cancela |
| `⚠️ RAG no disponible…` al arrancar la consola | `bash scripts/mn5/pedir_gpu.sh indice consola` |
| Construir el índice tarda decenas de minutos | El embedder corre en la CPU: pon `OLLAMA_EMBED_NUM_GPU=auto` en el `.env` de MN5 |
