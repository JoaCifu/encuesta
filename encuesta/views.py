from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse

from .forms import PasoForm
from .models import Bloque, Participante


def _participante(request):
    pid = request.session.get("participante")
    if not pid:
        return None
    return Participante.objects.filter(pk=pid).first()


def _respuestas(participante):
    return {r.pregunta.codigo: r.valor
            for r in participante.respuestas.select_related("pregunta")}


def _visibles(bloque, respuestas):
    return [p for p in bloque.preguntas.all() if p.es_visible(respuestas)]


def _vecino(bloques, respuestas, orden, paso):
    """Siguiente (paso=1) o anterior (paso=-1) bloque con preguntas visibles."""
    candidatos = [b for b in bloques if (b.orden - orden) * paso > 0]
    if paso < 0:
        candidatos.reverse()
    return next((b for b in candidatos if _visibles(b, respuestas)), None)


def _finalizar(participante, bloques):
    """Borra respuestas de preguntas que dejaron de ser visibles y cierra la encuesta."""
    respuestas = _respuestas(participante)
    visibles = {p.codigo for b in bloques for p in _visibles(b, respuestas)}
    participante.respuestas.exclude(pregunta__codigo__in=visibles).delete()
    participante.completado = True
    participante.save()


def inicio(request):
    primero = Bloque.objects.first()
    if primero is None:
        raise Http404("La encuesta aún no tiene preguntas. Ejecuta: python manage.py cargar_preguntas")

    error = None
    if request.method == "POST":
        if request.POST.get("consentimiento"):
            participante = _participante(request)
            if not participante or participante.completado:
                participante = Participante.objects.create()
                request.session["participante"] = str(participante.id)
            return redirect("encuesta:paso", orden=primero.orden)
        error = "Para continuar, acepta el uso de tus respuestas."
    return render(request, "encuesta/inicio.html", {"error": error})


def paso(request, orden):
    participante = _participante(request)
    if participante is None:
        return redirect("encuesta:inicio")
    if participante.completado:
        return redirect("encuesta:gracias")

    bloques = list(Bloque.objects.prefetch_related("preguntas__opciones"))
    bloque = next((b for b in bloques if b.orden == orden), None)
    if bloque is None:
        raise Http404

    respuestas = _respuestas(participante)
    visibles = _visibles(bloque, respuestas)
    if not visibles:  # paso sin preguntas aplicables: saltarlo
        direccion = -1 if request.GET.get("dir") == "atras" else 1
        destino = _vecino(bloques, respuestas, orden, direccion)
        if destino:
            url = reverse("encuesta:paso", args=[destino.orden])
            return redirect(url + ("?dir=atras" if direccion < 0 else ""))
        return redirect("encuesta:inicio")

    if request.method == "POST":
        form = PasoForm(request.POST, preguntas=visibles, respuestas=respuestas)
        if form.is_valid():
            form.guardar(participante)
            respuestas = _respuestas(participante)
            siguiente = _vecino(bloques, respuestas, orden, 1)
            if siguiente:
                return redirect("encuesta:paso", orden=siguiente.orden)
            _finalizar(participante, bloques)
            return redirect("encuesta:gracias")
    else:
        form = PasoForm(preguntas=visibles, respuestas=respuestas)

    anterior = _vecino(bloques, respuestas, orden, -1)
    activos = [b for b in bloques if _visibles(b, respuestas)]
    posicion = next((i for i, b in enumerate(activos, 1) if b.orden == orden), 1)
    return render(request, "encuesta/paso.html", {
        "bloque": bloque,
        "form": form,
        "anterior": anterior,
        "es_ultimo": _vecino(bloques, respuestas, orden, 1) is None,
        "posicion": posicion,
        "total": len(activos),
        "progreso": round((posicion - 1) / len(activos) * 100),
    })


def gracias(request):
    request.session.pop("participante", None)
    return render(request, "encuesta/gracias.html")
