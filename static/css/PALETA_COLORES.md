# Sistema de Diseño - Paleta de Colores

## Variables CSS Disponibles

###  Colores Primarios
```css
--primary: #1e40af;        /* Azul corporativo principal */
--primary-dark: #1e3a8a;   /* Azul oscuro para hover */
--primary-light: #3b82f6;  /* Azul claro para elementos secundarios */
```

### Colores Secundarios
```css
--secondary: #64748b;      /* Gris azulado para textos secundarios */
--accent: #f59e0b;         /* Naranja/Ámbar para llamadas a la acción */
```

###  Colores de Estado
```css
--success: #10b981;        /* Verde - Completado */
--warning: #f59e0b;        /* Ámbar - En progreso */
--danger: #ef4444;         /* Rojo - Atrasado/Urgente */
--info: #3b82f6;           /* Azul - Información */
--pending: #8b5cf6;        /* Púrpura - Pendiente */
```

###  Backgrounds
```css
--bg-primary: #ffffff;     /* Fondo principal */
--bg-secondary: #f8fafc;   /* Fondo alternativo */
--bg-tertiary: #f1f5f9;    /* Fondo de cards/secciones */
--bg-sidebar: #1e293b;     /* Fondo del sidebar oscuro */
```

### 📐 Bordes
```css
--border-light: #e2e8f0;   /* Bordes suaves */
--border-medium: #cbd5e1;  /* Bordes medios */
--border-dark: #94a3b8;    /* Bordes destacados */
```
### Textos
```css
--text-primary: #0f172a;   /* Texto principal */
--text-secondary: #475569; /* Texto secundario */
--text-tertiary: #94a3b8;  /* Texto terciario/placeholders */
--text-white: #ffffff;     /* Texto sobre fondos oscuros */
```

### Tablas
```css
--table-header: #f1f5f9;   /* Fondo encabezado de tabla */
--table-row-odd: #ffffff;  /* Fila impar */
--table-row-even: #f8fafc; /* Fila par (zebra striping) */
--table-hover: #e0f2fe;    /* Hover sobre fila */
--table-border: #e2e8f0;   /* Bordes de tabla */
```

###  Formularios
```css
--input-bg: #ffffff;       /* Fondo de inputs */
--input-border: #cbd5e1;   /* Borde normal */
--input-focus: #3b82f6;    /* Borde al hacer focus */
--input-disabled: #f1f5f9; /* Input deshabilitado */
--input-error: #fecaca;    /* Fondo de input con error */
```

### Sombras
```css
--shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
--shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
--shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
```

---

## Uso de Variables

### Ejemplo: Card
```css
.mi-card {
  background: var(--bg-primary);
  border: 1px solid var(--border-light);
  color: var(--text-primary);
  box-shadow: var(--shadow-sm);
}
```

### Ejemplo: Botón
```css
.mi-boton {
  background: var(--primary);
  color: var(--text-white);
  border: 1px solid var(--primary);
}
.mi-boton:hover {
  background: var(--primary-dark);
}
```

### Ejemplo: Badge de Estado
```css
.badge-completado {
  background: #d1fae5;
  color: #065f46;
}
```

---

## 📦 Clases Disponibles

### Badges
- `.badge--success` - Verde (completado)
- `.badge--warning` - Ámbar (en progreso)
- `.badge--danger` - Rojo (atrasado/urgente)
- `.badge--info` - Azul (información)
- `.badge--pending` - Púrpura (pendiente)
- `.badge--muted` - Gris (neutral)

### Botones
- `.btn.btn--primary` - Botón primario azul
- `.btn.btn--accent` - Botón de acento naranja
- `.btn.btn--ghost` - Botón con borde
- `.btn.btn--muted` - Botón neutral

### Cards
- `.card` - Card básico con sombra
- `.card-kpi` - Card para KPIs con hover

---

## 🎯 Mejoras Implementadas

1. **Sistema de variables semántico**: Nombres descriptivos que comunican el propósito
2. **Colores consistentes**: Paleta unificada en toda la aplicación
3. **Estados visuales**: Colores específicos para diferentes estados de tareas/proyectos
4. **Tablas mejoradas**: Zebra striping y hover states
5. **Formularios accesibles**: Estados de focus, disabled y error
6. **Sombras estandarizadas**: Tres niveles de elevación
7. **Transiciones suaves**: Animaciones en hover y focus
8. **Retrocompatibilidad**: Variables antiguas mantenidas para evitar romper código existente
