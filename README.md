# RuralH2O — Sistema de Monitoreo de Calidad de Agua Rural

> **Proyecto para Ingeniería Civil Informática - Universidad de Aysén.**
> Solución digital para el seguimiento normativo (NCh 409) de sistemas de agua en comunidades rurales de la Región de Aysén.

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)](https://www.python.org/)
[![MySQL](https://img.shields.io/badge/mysql-%2300f.svg?style=for-the-badge&logo=mysql&logoColor=white)](https://www.mysql.com/)

---

## 📖 Descripción General

`RuralH2O` nace como respuesta a la brecha de digitalización en el monitoreo de agua potable en zonas rurales. El sistema permite registrar parámetros críticos (pH, Cloro, Turbidez) y evaluar automáticamente si cumplen con la **Norma Chilena 409**, facilitando la toma de decisiones para los comités de agua.

### Características Principales
* **Gestión de Puntos de Monitoreo:** Registro georreferenciado de pozos, ríos y vertientes.
* **Validación Automática:** Motor de reglas basado en la NCh 409 (pH 6.5-8.5, Cloro ≤ 2.0, Turbidez ≤ 5.0).
* **Sistema de Alertas:** Generación automática de notificaciones ante mediciones fuera de norma.
* **Seguridad:** Autenticación de usuarios mediante **JWT** y encriptación **BCrypt**.
* **Documentación API:** Integración nativa con Swagger y Redoc.

---

## 🛠️ Stack Tecnológico

* **Lenguaje:** Python 3.x
* **Framework:** FastAPI
* **ORM:** SQLAlchemy
* **Base de Datos:** MySQL
* **Seguridad:** Passlib, Python-Jose (JWT)

---

## 🚀 Instalación y Configuración

### Requisitos Previos
* Python 3.10+
* Servidor MySQL activo

### Pasos
1.  **Clonar el repositorio:**
    ```bash
    git clone https://github.com/Drowslyy/RuralH2O-.git
    cd RuralH2O-
    ```

2.  **Crear entorno virtual:**
    ```bash
    python -m venv venv
    # En Windows:
    .\venv\Scripts\activate
    # En Linux/Mac:
    source venv/bin/activate
    ```

3.  **Instalar dependencias:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Variables de Entorno:**
    Edita `database.py` con tus credenciales locales o configura una variable de entorno:
    ```python
    DATABASE_URL = "mysql+pymysql://USUARIO:PASSWORD@localhost:3306/ruralh2o"
    ```

---

## 💻 Uso de la API

### Iniciar Servidor
```bash
uvicorn main:app --reload