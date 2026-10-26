import uuid

from django.db import models


class Bloque(models.Model):
    """Un paso de la encuesta (una página con una o más preguntas)."""

    orden = models.PositiveSmallIntegerField(unique=True)
    titulo = models.CharField(max_length=120)
    descripcion = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["orden"]

    def __str__(self):
        return f"{self.orden}. {self.titulo}"


class Pregunta(models.Model):
    class Tipo(models.TextChoices):
        UNICA = "unica", "Selección única"
        MULTIPLE = "multiple", "Selección múltiple"
        ESCALA = "escala", "Escala 1-5"
        MATRIZ = "matriz", "Escala 1-5 por ítem"
        RANKING = "ranking", "Ordenar de mayor a menor"
        TEXTO = "texto", "Texto libre"
        CONTACTO = "contacto", "Autorización de contacto"

    codigo = models.CharField(max_length=10, unique=True, help_text="Ej: P07")
    bloque = models.ForeignKey(Bloque, on_delete=models.CASCADE, related_name="preguntas")
    orden = models.PositiveSmallIntegerField()
    texto = models.CharField(max_length=300)
    ayuda = models.CharField(max_length=200, blank=True)
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    obligatoria = models.BooleanField(default=True)
    max_opciones = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Solo para selección múltiple."
    )

    # Lógica condicional (sin FKs, para mantenerlo simple):
    # la pregunta se muestra solo si la respuesta a `condicion_codigo`
    # empieza con alguno de los textos de `condicion_valores`.
    condicion_codigo = models.CharField(max_length=10, blank=True)
    condicion_valores = models.JSONField(default=list, blank=True)

    # Si se indica, las opciones salen de lo que la persona marcó en esa pregunta.
    opciones_de_codigo = models.CharField(max_length=10, blank=True)

    class Meta:
        ordering = ["bloque__orden", "orden"]

    def __str__(self):
        return f"{self.codigo} {self.texto[:60]}"

    def opciones_disponibles(self, respuestas):
        """Textos de opciones. `respuestas` es {codigo: valor} del participante."""
        if self.opciones_de_codigo:
            previo = respuestas.get(self.opciones_de_codigo) or []
            return [o for o in previo if not o.startswith("Ninguna")]
        return [o.texto for o in self.opciones.all()]

    def es_visible(self, respuestas):
        if self.condicion_codigo:
            valor = respuestas.get(self.condicion_codigo)
            valores = valor if isinstance(valor, list) else ([valor] if valor else [])
            prefijos = tuple(self.condicion_valores)
            if not any(str(v).startswith(prefijos) for v in valores):
                return False
        if self.opciones_de_codigo and not self.opciones_disponibles(respuestas):
            return False
        return True


class Opcion(models.Model):
    pregunta = models.ForeignKey(Pregunta, on_delete=models.CASCADE, related_name="opciones")
    orden = models.PositiveSmallIntegerField()
    texto = models.CharField(max_length=200)

    class Meta:
        ordering = ["orden"]

    def __str__(self):
        return self.texto


class Participante(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creado = models.DateTimeField(auto_now_add=True)
    completado = models.BooleanField(default=False)
    acepta_contacto = models.BooleanField(default=False)
    nombre = models.CharField(max_length=120, blank=True)
    contacto = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-creado"]

    def __str__(self):
        return f"{self.nombre or 'Anónimo'} ({str(self.id)[:8]})"


class Respuesta(models.Model):
    participante = models.ForeignKey(
        Participante, on_delete=models.CASCADE, related_name="respuestas"
    )
    pregunta = models.ForeignKey(Pregunta, on_delete=models.CASCADE, related_name="respuestas")
    # str, int, list o dict según el tipo de pregunta
    valor = models.JSONField()

    class Meta:
        unique_together = [("participante", "pregunta")]

    def __str__(self):
        return f"{self.pregunta.codigo}: {self.valor}"
