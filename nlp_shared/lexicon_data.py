"""Données lexicales — source unique pour le service NLP et Django."""

from __future__ import annotations

INCIDENT_TYPES = (
    "vol",
    "kidnapping",
    "agression",
    "violence",
    "vandalisme",
    "autre",
)

# (regex, label, confiance) — première correspondance avec la confiance la plus haute gagne
RULES: list[tuple[str, str, float]] = [
    # Violence armée / banditisme (priorité haute)
    (
        r"braquage|fusillade|\barmer?\b|\barmé\b|\barmes\b|attaque à main armée|"
        r"attaque armée|coups de feu|tir à|fusill|"
        r"bandit|voyou|assassin|kuluna|milicien|\bgang\b|terror|massacre|"
        r"menace.{0,25}arme|trop de bandit",
        "violence",
        0.90,
    ),
    (
        r"meurtre|assassinat|homicide|\bmort\b|\btué\b|\btue\b|"
        r"lynchage|exécution|exécuté|cadavre",
        "violence",
        0.92,
    ),
    # Enlèvement
    (
        r"kidnap|enlèvement|enlevement|\botage\b|ransom|séquestr|sequestr|"
        r"enlevé|enleve|prise d'otage",
        "kidnapping",
        0.88,
    ),
    # Vol / cambriolage
    (
        r"\bvol\b|cambriol|pickpocket|arrach|braqueur|voleur|"
        r"snatch|dévalis|devalis|porte forcée|vol à l'arraché|"
        r"vol de (téléphone|tel|portable|moto|vélo|sac)|"
        r"moto volée|téléphone volé",
        "vol",
        0.82,
    ),
    # Agression
    (
        r"agress|bagarre|coups|tabass|violence physique|"
        r"intimid|harcèl|harcel|rixe|bastonnade|"
        r"violence conjugale|agression sexuelle",
        "agression",
        0.80,
    ),
    (
        r"\bmenace\b|\bmenacé\b|\bmenaces\b",
        "agression",
        0.74,
    ),
    # Vandalisme
    (
        r"vandal|dégrad|degrad|détruit|detruit|\bcasse\b|incendi|pillag|"
        r"saccag|graffiti|\btags\b|voitures incendiées|biens publics",
        "vandalisme",
        0.78,
    ),
    # Insécurité générale / langage citoyen Kinshasa
    (
        r"insécur|insecur|dangereux|zone rouge|pas sûr|pas sur|"
        r"criminel|délinqu|delinqu|inquiétant|inquietant|"
        r"c'est chaud|cest chaud|on n'ose plus|plus oser sortir|"
        r"terroris|terrif|peur de sortir|inhabitable",
        "violence",
        0.74,
    ),
    # Transport / routes (contexte Kinshasa)
    (
        r"route bloquée|barricad|embouteillage.{0,30}(bandit|kuluna|armé)|"
        r"attaque.{0,40}(bus|wewa|ketch|taxi)",
        "violence",
        0.76,
    ),
]

# Filtre anodin strict (tests, blagues) — appliqué même sans marqueur local
BENIGN_STRICT_PATTERNS: list[str] = [
    r"\bcanard\b",
    r"\bblague\b",
    r"rien à signaler",
    r"^j'?ai vu un\s+(canard|rien|chat|chien|oiseau|fantôme|fantome)\b",
    r"^c'?est un test\b",
    r"^test\s*$",
    r"^\s*hello\s*$",
    r"^\s*bonjour\s*$",
    r"^aaa+\s*$",
    r"tout va bien",
    r"pas de problème",
    r"aucun incident",
    r"pas.{0,30}dangere",
    r"rien.{0,20}dangere",
    r"aucun danger",
    r"sans danger",
    r"ce n'?est pas dangere",
    r"c'?est pas dangere",
    r"pas du tout dangere",
    r"pas si dangere",
    r"pas vraiment dangere",
]

# Actualités / hors périmètre — ignorées si marqueurs d'incident local présents
BENIGN_CONTEXT_PATTERNS: list[str] = [
  # Institutionnel / politique RDC
    r"\bcndh\b|commission nationale des droits|diplomat",
    r"séance de travail|représentation diplomatique",
    r"permis de conduire|réforme.{0,40}(administratif|biométrique)",
    r"vice-premier ministre|contrôle parlementaire",
    r"procès.{0,50}tribunal|bourgmestre.{0,40}démolition|kermesse",
    r"loi référendaire|coalition c\d+|sit-in de l'opposition",
    r"rdc[\s\-]?pass|identification numérique|identité numérique",
    r"identifiant national|carte d'identité biométrique",
    r"transformation numérique|nation digitale|économie numérique",
    r"gouvernement numérique|administration numérique|souveraineté numérique",
    r"lancement officiel|inauguration officielle|cérémonie de lancement",
    r"chef de l'?état.{0,120}(lancement|inauguration|procédé|déclaré|affirmé)",
    r"président.{0,120}(lancement|inauguration|procédé|déclaré|affirmé)",
    r"ministre.{0,80}(lancement|présenté|dévoilé|inaugure)",
    r"lancement officiel.{0,80}(rdc|pass|numérique|identification)",
  # Culture / divertissement
    r"\b(chanteur|chanteuse|musicien|musique|rumba|concert|tournée|tournee|"
    r"album|clip|remix|interview|droits d[’']auteur|auteur[- ]compositeur|"
    r"festival|spectacle|sc[eé]nique|maison de production)\b",
    r"\b(visa|visas)\b.{0,60}\b(ambassade|consulat)\b",
    r"\b(ambassade|consulat)\b.{0,60}\b(visa|visas)\b",
  # Conflit Est / reportages nationaux sans incident local
    r"partie est|est du pays|\bm23\b|\bafc\b|"
    r"violations? des droits humains|exécutions sommaires|"
    r"zones? de conflit|ituri|nord-kivu|beni\b|butembo",
  # Sport / économie / météo (hors sécurité urbaine)
    r"\b(match|football|basket|championnat|ligue des champions)\b",
    r"\b(bourse|inflation|taux de change|investissement)\b",
    r"\b(météo|pluie|inondation.{0,30}prévision)\b",
  # Cyber / arnaques en ligne (hors rue)
    r"ransomware|phishing|arnaque (en ligne|internet|en ligne)|crypto.?arnaque",
]

# Compatibilité : liste plate pour le classifieur NLP (strict + contexte)
BENIGN_PATTERNS: list[str] = BENIGN_STRICT_PATTERNS + BENIGN_CONTEXT_PATTERNS

# Marqueurs d'incident local — empêchent le filtre contextuel de rejeter à tort
LOCAL_INCIDENT_MARKERS: list[str] = [
    r"braquage|kuluna|agress|bagarre|\bvol\b|cambriol|kidnap|fusillade|"
    r"\btir\b|bless|fusill|enlèvement|enlevement|bandit|voyou|assassin|criminel|"
    r"voyous|coups de feu|\barmé\b|menace.{0,20}arme|pickpocket|vandal|"
    r"insécur|zone rouge|pas sûr|pas sur",
]

# Mots-clés fusion Django (alerte critique / vigilance)
HIGH_RISK_KEYWORD_PATTERN = (
    r"meurtre|assassinat|assassin|homicide|kidnap|enlèvement|enlevement|braquage|"
    r"fusillade|\barmer?\b|armé|terror|massacre|\bviolence\b|\bmort\b|"
    r"\btué\b|\btue\b|\bsang\b|\bdanger\b|"
    r"\bbandit\b|\bvoyou\b|\bcriminel\b|\bgang\b|\bkuluna\b"
)

MEDIUM_RISK_KEYWORD_PATTERN = (
    r"agress|bagarre|\bvol\b|cambriol|vandal|incendie|accident|bless"
)

SEED_SAMPLES: list[tuple[str, str]] = [
    # Violence / banditisme
    ("braquage armé à Limete", "violence"),
    ("fusillade et violence à Kisenso", "violence"),
    ("attaque à main armée dans la rue", "violence"),
    ("Il y a trop de bandit, des voyous et des assassins ici", "violence"),
    ("zone dangereuse avec des kulunas la nuit", "violence"),
    ("menace avec arme au quartier", "violence"),
    ("coups de feu entendus à Matete", "violence"),
    ("gang de voyous terrorise les passants", "violence"),
    ("insécurité totale dans ce coin", "violence"),
    ("meurtre signalé à Ngaba", "violence"),
    ("manifestation dégénérée en violence", "violence"),
    ("c'est chaud dans ce quartier on n'ose plus sortir", "violence"),
    ("criminels armés dans le quartier de Maluku", "violence"),
    # Vol
    ("vol de téléphone à Gombe", "vol"),
    ("cambriolage à la maison", "vol"),
    ("pickpocket à l'arrêt de bus", "vol"),
    ("arracheur de sac à Kinshasa", "vol"),
    ("voleur de moto dans la rue", "vol"),
    ("vol à l'arraché Limete", "vol"),
    # Kidnapping
    ("kidnapping signalé à Matete", "kidnapping"),
    ("enlèvement d'un citoyen", "kidnapping"),
    ("tentative d'enlèvement à Ndjili", "kidnapping"),
    ("enlèvement sur la route de Maluku", "kidnapping"),
    # Agression
    ("agression dans la rue à Bandal", "agression"),
    ("bagarre et coups entre jeunes", "agression"),
    ("tabassé par des inconnus", "agression"),
    ("menaces et intimidation", "agression"),
    ("agression sexuelle signalée", "agression"),
    # Vandalisme
    ("vandalisme de véhicules à Ngaba", "vandalisme"),
    ("destruction de biens publics", "vandalisme"),
    ("voitures incendiées au quartier", "vandalisme"),
    ("dégradation des panneaux publics", "vandalisme"),
    # Non sécurité / institutionnel
    ("incident non classé", "autre"),
    ("ransomware et arnaque internet", "autre"),
    ("lancement officiel du RDC-PASS identification numérique à Kinshasa", "autre"),
    ("transformation numérique et modernisation des services publics", "autre"),
    ("président inaugure un projet administratif national", "autre"),
    ("commission nationale des droits de l'homme séance de travail", "autre"),
    ("permis de conduire biométrique réforme administrative", "autre"),
    ("j'ai vu un canard dans la rue", "autre"),
    ("c'est un test", "autre"),
    ("rien à signaler tout va bien", "autre"),
    ("le chanteur Fally Ipupa en concert à Paris", "autre"),
    ("match de football Real Madrid contre Barcelona", "autre"),
    ("violations des droits humains dans l'Ituri selon la CNDH", "autre"),
    # Variantes locales
    ("kuluna attaque les passants à Kimbanseke", "violence"),
    ("braquage à la station Total", "violence"),
    ("cambriolage nocturne Masina", "vol"),
    ("fusillade entre bandits", "violence"),
    ("zone rouge pas sûr de sortir", "violence"),
]
