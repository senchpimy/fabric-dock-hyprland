# Hyprland Animated Icon Dock

Un dock de iconos animado y ligero para Hyprland que muestra las ventanas abiertas.

## Características

-   **Efecto de Lupa**: Los iconos se agrandan suavemente al pasar el ratón por encima.
-   **Animaciones Fluidas**: El dock aparece y desaparece con una animación gradual.
-   **Enfoque de Ventanas**: Un solo clic en un icono enfoca la ventana correspondiente.
-   **Ligero y Personalizable**: Bajo consumo de recursos y fácil de modificar.

## Uso

Para ejecutar el dock, simplemente corre el script:

```bash
python main.py
```

## Personalización

```python
# --- Constantes de Configuración ---
MAX_ICON_SIZE = 96          # Tamaño máximo del icono.
AFFECT_DISTANCE = 150       # Distancia a la que el ratón afecta a los iconos.
ANIMATION_INTERVAL_MS = 15  # Intervalo de la animación (ms, más bajo = más suave).
ANIMATION_STEP = 2          # Velocidad/pasos de la animación.
```
