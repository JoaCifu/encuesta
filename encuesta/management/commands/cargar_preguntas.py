from django.core.management.base import BaseCommand
from django.db import transaction

from encuesta.models import Bloque, Opcion, Pregunta

U, M, E, X, R, T, C = "unica", "multiple", "escala", "matriz", "ranking", "texto", "contacto"

RANGOS_CLP = [
    "Menos de $500.000",
    "$500.000 a $1.500.000",
    "$1.500.000 a $4.000.000",
    "$4.000.000 a $10.000.000",
    "Más de $10.000.000",
]

DOLORES = [
    "Procesos que dependen de Excel, correos o WhatsApp",
    "Tareas manuales repetitivas",
    "Falta de claridad sobre quién hace qué en un proceso",
    "Decisiones tomadas sin datos o con datos poco confiables",
    "Reportes que toman mucho tiempo en armarse",
    "Software a medida que no existe o no calza con lo que necesitamos",
    "Sistemas que no se conectan entre sí",
]

BLOQUES = [
    (1, "Perfil", "Para entender desde qué lugar respondes."),
    (2, "Dolores y necesidades", "Qué situaciones viven hoy en tu organización."),
    (3, "Prioridad", "Sobre lo que marcaste en el paso anterior."),
    (4, "Experiencia previa", ""),
    (5, "Tu experiencia con proveedores", "Cuéntame cómo fue, con franqueza."),
    (6, "Interés en los servicios", ""),
    (7, "Uso de inteligencia artificial", "Tres preguntas rápidas."),
    (8, "Confianza y decisión de compra", "Lo más útil de toda la encuesta."),
    (9, "Cierre", "Última página."),
]

# (codigo, bloque, tipo, texto, opciones, extras)
PREGUNTAS = [
    ("P01", 1, U, "¿Cuál describe mejor tu situación actual?", [
        "Dueño/a o socio/a de empresa", "Gerente / director/a",
        "Jefatura o profesional con poder de decisión parcial",
        "Profesional sin decisión de compra", "Independiente / freelance", "Otro"], {}),
    ("P02", 1, U, "¿Cuántas personas tiene la organización donde trabajas o que diriges?",
     ["1-10", "11-50", "51-200", "201-1.000", "Más de 1.000"], {}),
    ("P03", 1, U, "¿En qué rubro trabajas?", [
        "Tecnología", "Servicios profesionales", "Finanzas y seguros", "Salud", "Educación",
        "Comercio y retail", "Industria y manufactura", "Minería y energía",
        "Construcción e inmobiliario", "Logística y transporte", "Sector público", "Otro"], {}),

    ("P04", 2, M, "¿Cuáles de estas situaciones existen hoy en tu organización?",
     DOLORES + ["Ninguna de las anteriores"], {"ayuda": "Marca todas las que apliquen."}),
    ("P05", 3, U, "De las que marcaste, ¿cuál es la que más te complica hoy?", [],
     {"opciones_de_codigo": "P04"}),
    ("P06", 3, E, "¿Qué tan prioritario es resolverla en los próximos 12 meses?", [],
     {"ayuda": "1 = nada prioritario, 5 = muy prioritario.",
      "condicion_codigo": "P04", "condicion_valores": DOLORES}),

    ("P07", 4, U, "En los últimos 2 años, ¿has contratado o intentado resolver algo así?", [
        "Sí, con una consultora o empresa externa", "Sí, con un freelance",
        "Sí, con una herramienta o software (SaaS)", "Sí, con el equipo interno",
        "Lo intentamos, pero no se concretó", "No"], {}),

    ("P08", 5, M, "¿Qué tipo de servicio fue?", [
        "Procesos / BPM", "Datos y reportería", "Ciencia de datos",
        "Aplicación web", "Automatización", "Otro"],
     {"condicion_codigo": "P07", "condicion_valores": ["Sí"]}),
    ("P09", 5, U, "¿Aproximadamente cuánto se invirtió?", RANGOS_CLP + ["No lo sé"],
     {"condicion_codigo": "P07", "condicion_valores": ["Sí"]}),
    ("P10", 5, E, "¿Qué tan satisfecho/a quedaste?",  [],
     {"ayuda": "1 = nada satisfecho, 5 = muy satisfecho.",
      "condicion_codigo": "P07", "condicion_valores": ["Sí"]}),
    ("P11", 5, T, "¿Qué cambiarías de esa experiencia o del proveedor?", [],
     {"obligatoria": False, "condicion_codigo": "P07", "condicion_valores": ["Sí"]}),
    ("P12", 5, U, "¿Cómo encontraste a ese proveedor o solución?", [
        "Referido", "Búsqueda en internet", "LinkedIn", "Evento", "Ya lo conocía", "Otro"],
     {"condicion_codigo": "P07", "condicion_valores": ["Sí"]}),
    ("P13", 5, U, "¿Sigues trabajando con ese proveedor?", [
        "Sí", "No, lo dejamos por precio", "No, por resultados o calidad",
        "No, el proyecto terminó"],
     {"condicion_codigo": "P07", "condicion_valores": ["Sí"]}),
    ("P14", 5, M, "¿Por qué no?", [
        "No lo necesitamos hoy", "No hay presupuesto", "No sabíamos a quién contratar",
        "Preferimos resolverlo internamente", "Desconfianza o malas experiencias previas",
        "Otro"],
     {"condicion_codigo": "P07", "condicion_valores": ["No", "Lo intentamos"]}),

    ("P15", 6, X, "¿Cuánto valor tendría para ti resolver cada uno de estos puntos?", [
        "Dejar claro quién hace qué en cada proceso y dónde se pierde tiempo",
        "Tener reportes y gráficos que se actualicen solos, sin armarlos a mano",
        "Anticipar ventas, demanda o riesgos usando los datos de la empresa",
        "Tener un sistema o aplicación web hecho a la medida de cómo trabaja mi empresa",
        "Eliminar tareas manuales y repetitivas (copiar datos, enviar correos, revisar planillas)",
        "Que mi equipo aprenda a usar IA en su trabajo diario",
        "Usar IA para resolver tareas que hoy toman horas (resumir, clasificar, responder)",
        "Un asistente de IA que responda con la información de mi propia empresa"],
     {"ayuda": "1 = ningún valor, 5 = mucho valor."}),
    ("P16", 6, M, "¿Con qué formato te sentirías más cómodo/a?", [
        "Diagnóstico corto con informe y recomendaciones",
        "Proyecto cerrado con alcance y precio fijo",
        "Horas de consultoría bajo demanda",
        "Servicio mensual continuo",
        "Capacitación o taller para mi equipo"],
     {"max_opciones": 2, "ayuda": "Elige hasta 2."}),
    ("P17", 6, U, "Para un primer proyecto, ¿qué rango de inversión te parecería razonable?",
     RANGOS_CLP, {}),

    ("P27", 7, U, "¿Usas herramientas de IA (ChatGPT, Copilot, Gemini u otras) en tu trabajo?", [
        "Nunca", "Las he probado", "Las uso cada semana", "Las uso a diario"], {}),
    ("P28", 7, M, "¿Para qué las usas?", [
        "Redactar o resumir textos", "Analizar datos", "Programar",
        "Atención a clientes", "Buscar información", "Otro"],
     {"obligatoria": False, "ayuda": "Si no las usas, puedes saltar esta pregunta."}),
    ("P29", 7, M, "¿Qué te frena de usarlas más, o de partir?", [
        "No sé por dónde partir", "Preocupación por la confidencialidad de los datos",
        "En mi organización no hay política o autorización", "Los resultados son poco confiables",
        "Falta de capacitación", "Nada me frena", "Otro"],
     {"ayuda": "Marca todas las que apliquen."}),

    ("P18", 8, M, "¿Qué te daría más confianza para contratar a un proveedor de este tipo?", [
        "Casos de éxito con resultados medibles", "Referencia de alguien que conozco",
        "Reunión o diagnóstico inicial sin costo", "Demo o prototipo rápido antes de contratar",
        "Propuesta clara con alcance, plazos y precio fijo", "Garantía o cláusula de salida",
        "Certificaciones o formación formal", "Experiencia previa en mi rubro",
        "Presencia profesional (web, LinkedIn, contenido)",
        "Que explique las cosas sin tecnicismos"],
     {"max_opciones": 3, "ayuda": "Elige las 3 más importantes."}),
    ("P19", 8, M, "¿Qué te haría desconfiar o descartar a un proveedor?", [
        "Promesas muy grandes sin evidencia", "Falta de claridad en precios o alcance",
        "Jerga técnica excesiva", "Que sea una sola persona (riesgo de dependencia)",
        "No tener experiencia en mi rubro", "Falta de documentación y traspaso", "Otro"], {}),
    ("P20", 8, X, "Al decidir, ¿qué tan importante es cada uno de estos factores?", [
        "Precio", "Confianza en la persona", "Experiencia comprobable",
        "Rapidez", "Cercanía y atención", "Tecnología utilizada"],
     {"ayuda": "1 = poco importante, 5 = muy importante. Puedes repetir valores o dejar en blanco los que no sepas.",
      "obligatoria": False}),

    ("P23", 9, T, "Si hoy me conocieras solo como «excompañero que hace consultoría», ¿qué sería lo primero que querrías saber de mí antes de considerarme?", [], {}),
    ("P24", 9, T, "¿Hay algún problema o servicio que no mencioné y que te gustaría ver resuelto?", [],
     {"obligatoria": False}),
    ("P25", 9, U, "¿Conoces a alguien (persona o empresa) que podría tener estas necesidades y que estarías dispuesto/a a presentarme?",
     ["Sí", "Quizás", "No"], {}),
    ("P26", 9, C, "¿Te puedo contactar para una conversación de 15 minutos para profundizar en tus respuestas?",
     ["Sí", "No"], {"ayuda": "Si respondes que sí, déjame tu nombre y un medio de contacto."}),
]


class Command(BaseCommand):
    help = "Carga (o actualiza) los bloques, preguntas y opciones de la encuesta."

    @transaction.atomic
    def handle(self, *args, **options):
        bloques = {}
        for orden, titulo, desc in BLOQUES:
            bloques[orden], _ = Bloque.objects.update_or_create(
                orden=orden, defaults={"titulo": titulo, "descripcion": desc})

        for i, (codigo, b, tipo, texto, opciones, extra) in enumerate(PREGUNTAS, 1):
            p, _ = Pregunta.objects.update_or_create(codigo=codigo, defaults={
                "bloque": bloques[b], "orden": i, "tipo": tipo, "texto": texto,
                "ayuda": extra.get("ayuda", ""),
                "obligatoria": extra.get("obligatoria", True),
                "max_opciones": extra.get("max_opciones"),
                "condicion_codigo": extra.get("condicion_codigo", ""),
                "condicion_valores": extra.get("condicion_valores", []),
                "opciones_de_codigo": extra.get("opciones_de_codigo", ""),
            })
            p.opciones.all().delete()
            Opcion.objects.bulk_create(
                Opcion(pregunta=p, orden=j, texto=t) for j, t in enumerate(opciones, 1))

        # Elimina preguntas y bloques que ya no están en la definición
        codigos = [q[0] for q in PREGUNTAS]
        borradas, _ = Pregunta.objects.exclude(codigo__in=codigos).delete()
        Bloque.objects.exclude(orden__in=[b[0] for b in BLOQUES]).delete()
        if borradas:
            self.stdout.write(f"Se eliminaron preguntas obsoletas (y sus respuestas): {borradas} registros.")

        self.stdout.write(self.style.SUCCESS(
            f"{len(BLOQUES)} bloques y {len(PREGUNTAS)} preguntas cargadas."))
