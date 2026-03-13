BASE_URL = "https://geo.api.gouv.fr"

# --- [6] RESOURCES passe de liste à dict {resource: fields}.
#     Clé = endpoint API, valeur = CSV des champs utiles au projet.
#     Seuls les champs documentés dans ingestion-geo.md sont listés —
#     ça évite de télécharger contour, siren, codeEpci, etc.
RESOURCES = {
    "regions": "code,nom,zone",
    "departements": "code,nom,codeRegion,zone",
    "communes": "code,nom,codesPostaux,codeDepartement,codeRegion,population,centre,surface",
}
