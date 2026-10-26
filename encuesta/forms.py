from django import forms

from .models import Pregunta

T = Pregunta.Tipo
ESCALA = [(str(i), str(i)) for i in range(1, 6)]


class PasoForm(forms.Form):
    """Formulario dinámico: un campo (o grupo de campos) por pregunta visible."""

    def __init__(self, *args, preguntas, respuestas, **kwargs):
        super().__init__(*args, **kwargs)
        self.preguntas = preguntas
        self.respuestas = respuestas
        self.campos = {}  # codigo -> [nombres de campo]
        for p in preguntas:
            self._crear(p)

    # ---------- construcción ----------
    def _crear(self, p):
        previo = self.respuestas.get(p.codigo)
        req = p.obligatoria
        opts = p.opciones_disponibles(self.respuestas)
        choices = [(o, o) for o in opts]
        c = p.codigo

        if p.tipo == T.UNICA:
            self.fields[c] = forms.ChoiceField(
                choices=choices, widget=forms.RadioSelect, required=req, initial=previo
            )
            self.campos[c] = [c]

        elif p.tipo == T.MULTIPLE:
            self.fields[c] = forms.MultipleChoiceField(
                choices=choices, widget=forms.CheckboxSelectMultiple,
                required=req, initial=previo or [],
            )
            self.campos[c] = [c]

        elif p.tipo == T.ESCALA:
            self.fields[c] = forms.ChoiceField(
                choices=ESCALA, widget=forms.RadioSelect, required=req,
                initial=str(previo) if previo else None,
            )
            self.campos[c] = [c]

        elif p.tipo == T.TEXTO:
            self.fields[c] = forms.CharField(
                widget=forms.Textarea(attrs={"rows": 3}), max_length=1000,
                required=req, initial=previo or "",
            )
            self.campos[c] = [c]

        elif p.tipo == T.MATRIZ:
            previo = previo or {}
            self.campos[c] = []
            for i, o in enumerate(opts):
                n = f"{c}__{i}"
                self.fields[n] = forms.ChoiceField(
                    choices=ESCALA, widget=forms.RadioSelect, required=req, label=o,
                    initial=str(previo[o]) if o in previo else None,
                )
                self.campos[c].append(n)

        elif p.tipo == T.RANKING:
            previo = previo or []
            posiciones = [("", "—")] + [(str(k), str(k)) for k in range(1, len(opts) + 1)]
            self.campos[c] = []
            for i, o in enumerate(opts):
                n = f"{c}__{i}"
                self.fields[n] = forms.ChoiceField(
                    choices=posiciones, required=req, label=o,
                    initial=str(previo.index(o) + 1) if o in previo else "",
                )
                self.campos[c].append(n)

        elif p.tipo == T.CONTACTO:
            self.fields[c] = forms.ChoiceField(
                choices=choices, widget=forms.RadioSelect, required=req, initial=previo
            )
            self.fields[f"{c}__nombre"] = forms.CharField(
                label="Nombre", max_length=120, required=False)
            self.fields[f"{c}__contacto"] = forms.CharField(
                label="Correo o teléfono", max_length=200, required=False)
            self.campos[c] = [c, f"{c}__nombre", f"{c}__contacto"]

    def grupos(self):
        """[(pregunta, [BoundField, ...])] para la plantilla."""
        return [(p, [self[n] for n in self.campos[p.codigo]]) for p in self.preguntas]

    # ---------- validación ----------
    def clean(self):
        datos = super().clean()
        for p in self.preguntas:
            nombres = self.campos[p.codigo]
            if p.tipo == T.MULTIPLE and p.max_opciones:
                if len(datos.get(nombres[0]) or []) > p.max_opciones:
                    self.add_error(nombres[0], f"Elige como máximo {p.max_opciones}.")
            elif p.tipo == T.RANKING:
                vals = [datos.get(n) for n in nombres]
                if any(vals):
                    if not all(vals):
                        self.add_error(nombres[0], "Asigna una posición a cada ítem.")
                    elif len(set(vals)) != len(vals):
                        self.add_error(nombres[0], "No repitas posiciones.")
            elif p.tipo == T.CONTACTO:
                if datos.get(nombres[0]) == "Sí" and not datos.get(nombres[2]):
                    self.add_error(nombres[2], "Indica un medio de contacto.")
        return datos

    # ---------- persistencia ----------
    def guardar(self, participante):
        d = self.cleaned_data
        for p in self.preguntas:
            nombres = self.campos[p.codigo]
            opts = p.opciones_disponibles(self.respuestas)
            valor = None

            if p.tipo in (T.UNICA, T.TEXTO):
                valor = d.get(nombres[0]) or None
            elif p.tipo == T.MULTIPLE:
                valor = d.get(nombres[0]) or None
            elif p.tipo == T.ESCALA:
                v = d.get(nombres[0])
                valor = int(v) if v else None
            elif p.tipo == T.MATRIZ:
                valor = {o: int(d[n]) for o, n in zip(opts, nombres) if d.get(n)} or None
            elif p.tipo == T.RANKING:
                pares = [(int(d[n]), o) for o, n in zip(opts, nombres) if d.get(n)]
                valor = [o for _, o in sorted(pares)] or None
            elif p.tipo == T.CONTACTO:
                valor = d.get(nombres[0]) or None
                participante.acepta_contacto = valor == "Sí"
                participante.nombre = d.get(nombres[1], "") if participante.acepta_contacto else ""
                participante.contacto = d.get(nombres[2], "") if participante.acepta_contacto else ""
                participante.save()

            if valor is None:
                participante.respuestas.filter(pregunta=p).delete()
            else:
                participante.respuestas.update_or_create(pregunta=p, defaults={"valor": valor})
