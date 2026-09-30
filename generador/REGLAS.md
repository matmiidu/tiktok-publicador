# Reglas de los videos

Todo lo que el dueño del canal fue pidiendo, en un solo lugar. Se leen antes de
escribir o rehacer cualquier historia, y cada comentario nuevo del panel de
revisión se agrega aquí. Un comentario sobre un video vale para todos.

## Contenido

- **Historias reales de Reddit, no inventadas.** Se buscan hilos por cuenta
  propia (tops históricos de r/AskReddit y subreddits de relatos: r/tifu,
  r/ProRevenge, r/MaliciousCompliance, r/BestofRedditorUpdates, etc.) y se
  eligen las respuestas más votadas.
- **Que sean impactantes de verdad**, de las que dejan con la boca abierta. Lo
  solamente curioso no basta. Conviene mirar más allá del top 10 de cada hilo.
- **Temas amplios.** Los ejemplos del dueño (médicos, disputas familiares,
  asesinos en serie, lecciones de vida) son solo ejemplos: sirve cualquier
  tema con experiencias personales interesantes.
- Se evitan el suicidio y la muerte de niños, porque TikTok les baja el alcance.
- **Adaptación fiel:** se traduce y se recorta, pero no se inventan hechos.
- **No acortar de más las historias individuales.** Se sacan solo el relleno y
  las repeticiones; si el original es corto, que quede corto.
- **Dar contexto** (comentario en el panel, 2026-09-30). Cuando aparece una
  persona, un lugar, una época o un término que el público puede no conocer,
  se explica en una frase: quién era y qué hizo (por ejemplo, Ted Bundy), dónde
  queda el lugar, qué fue la ley seca. Nada debe quedar "interpretativo". Lo
  que se agrega tiene que ser un hecho comprobable, no un adorno.

## Idioma

- **Español neutro, sin modismos:** "esposa" y no "señora", "traje" y no
  "terno", "alquilar" y no "arrendar", "conducir" y no "manejar"; nada de
  "súper", "al tiro" ni "po".
- Unidades métricas: °F pasa a °C, millas a km, libras a kg.

## Estructura

- **Varias respuestas:** no se narra "primera, segunda y tercera respuesta".
  Cada respuesta aparece arriba como comentario de Reddit, con los votos
  reales, mientras se narra, y cada una lleva **otra voz**.
- **Sin nombres de usuario en pantalla** (2026-09-30). La tarjeta de cada
  comentario dice "Usuario de Reddit", con el subreddit y los votos reales. El
  nombre real se guarda en el .txt solo como registro, y el enlace al hilo va
  en la descripción. Motivo: no exponer a los autores de historias personales.
- **Una sola historia:** se narra de corrido, con una voz acorde a quien la
  cuenta (voz de mujer si la narradora es mujer).
- **Actualizaciones:** si hay una, se dice "Actualización"; si hay varias,
  "Primera actualización", "Segunda actualización"… Si la escribe otra persona
  (por ejemplo, el esposo cuenta su versión), va con una voz acorde.
- **La pregunta final no va siempre**, solo en algunos videos, donde invite de
  verdad a comentar.

## Voz y ritmo

- **Solo tres voces:** es-US-AlonsoNeural (hombre), es-MX-DaliaNeural (mujer) y
  es-MX-JorgeNeural (hombre; lee el título y también narra). Se intercalan.
  Gonzalo (es-CO) no gusta. Paloma (es-US) no se ha evaluado.
- **Pausas cortas:** el silencio entre palabras se recorta a 0,15 s
  (`PAUSA_MAX` en hacer_video.py), porque las pausas largas espantan al
  público de TikTok.

## Formato visual (aprobado tal cual)

- Fondo de parkour de Minecraft vertical, con licencia CC BY y crédito en la
  descripción; tarjeta blanca con la pregunta al inicio; subtítulos grandes
  palabra por palabra, con la palabra actual en amarillo.

## Descripción para TikTok (2026-09-30)

- Cada video lleva su propia descripción: una o dos frases gancho que
  adelanten lo más fuerte de la historia sin contar el final, y un emoji como
  mucho.
- Entre 5 y 7 hashtags: los del tema (#truecrime, #medicina, #venganza,
  #adn…), los del formato (#historiasdereddit, #reddit, #storytime,
  #historiasreales) y #parati. Se evitan los genéricos que no dicen nada
  (#viral, #fyp repetido) y los que no tienen que ver con el video.
- En el .txt van como `# descripcion:` y `# hashtags:`. El generador agrega
  después los enlaces a los hilos y el crédito del gameplay.

## Flujo

- Nada va a TikTok sin estar aprobado en el panel de revisión. Lo aprobado se
  agrega a `cola.txt`, y la tarea diaria lo sube (máximo 5 por día).
