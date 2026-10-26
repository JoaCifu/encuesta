import csv

from django.contrib import admin
from django.http import HttpResponse

from .models import Bloque, Opcion, Participante, Pregunta, Respuesta


class OpcionInline(admin.TabularInline):
    model = Opcion
    extra = 0


@admin.register(Bloque)
class BloqueAdmin(admin.ModelAdmin):
    list_display = ("orden", "titulo")


@admin.register(Pregunta)
class PreguntaAdmin(admin.ModelAdmin):
    list_display = ("codigo", "bloque", "tipo", "texto")
    list_filter = ("bloque", "tipo")
    inlines = [OpcionInline]


class RespuestaInline(admin.TabularInline):
    model = Respuesta
    extra = 0
    can_delete = False
    readonly_fields = ("pregunta", "valor")


@admin.action(description="Exportar seleccionados a CSV (una fila por participante)")
def exportar_csv(modeladmin, request, queryset):
    # Columnas: (código, subclave, encabezado). Las matrices se abren por ítem.
    columnas = []
    for p in Pregunta.objects.prefetch_related("opciones"):
        if p.tipo == "matriz":
            columnas += [(p.codigo, o.texto, f"{p.codigo}__{o.texto}") for o in p.opciones.all()]
        else:
            columnas.append((p.codigo, None, p.codigo))

    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="encuesta.csv"'
    resp.write("\ufeff")  # para que Excel lea bien los acentos
    w = csv.writer(resp)
    w.writerow(["id", "creado", "completado", "acepta_contacto"] + [c[2] for c in columnas])

    for part in queryset.prefetch_related("respuestas__pregunta"):
        por_codigo = {r.pregunta.codigo: r.valor for r in part.respuestas.all()}
        fila = [part.id, part.creado.isoformat(), part.completado, part.acepta_contacto]
        for codigo, sub, _ in columnas:
            v = por_codigo.get(codigo, "")
            if sub is not None:
                v = (v or {}).get(sub, "")
            elif isinstance(v, list):
                v = " | ".join(v)
            fila.append(v)
        w.writerow(fila)
    return resp


@admin.register(Participante)
class ParticipanteAdmin(admin.ModelAdmin):
    list_display = ("__str__", "creado", "completado", "acepta_contacto")
    list_filter = ("completado", "acepta_contacto")
    inlines = [RespuestaInline]
    actions = [exportar_csv]
