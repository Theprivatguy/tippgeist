"""Eingebaute Übungstexte.

Alle Texte sind eigens für dieses Projekt geschrieben – ein Absatz, keine
Zeilenumbrüche, gemischte Länge. Wer eigene Texte tippen will, nimmt --file.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class TextItem:
    id: str
    title: str
    lang: str
    body: str

    @property
    def length(self) -> int:
        return len(self.body)


TEXTS: List[TextItem] = [
    TextItem(
        id="montag",
        title="Montagmorgen",
        lang="en",
        body=(
            "Monday morning, the build is green, the coffee is hot, and nothing "
            "has broken yet. Enjoy it. This state of the world has a half life "
            "of roughly eleven minutes."
        ),
    ),
    TextItem(
        id="server",
        title="Der Serverraum",
        lang="en",
        body=(
            "The server room is the coldest place in the building and the only "
            "one where nobody schedules a meeting. Engineers go there to think. "
            "The fans drown out everything, including the sound of a deployment "
            "going quietly wrong upstairs."
        ),
    ),
    TextItem(
        id="nacht",
        title="Nachts im Büro",
        lang="de",
        body=(
            "Nachts um halb zwei ist das Büro ein anderer Ort. Die Klimaanlage "
            "seufzt, der Drucker träumt von Papierstaus, und irgendwo blinkt eine "
            "Leuchtdiode, die dort tagsüber niemand bemerkt. Wer jetzt noch tippt, "
            "tippt schneller als am Vormittag, weil ihm sonst niemand zusieht."
        ),
    ),
    TextItem(
        id="ente",
        title="Die Quietscheente",
        lang="en",
        body=(
            "The rubber duck on my desk has solved more bugs than any debugger. "
            "It never interrupts, never suggests a rewrite, and never asks why "
            "the function is four hundred lines long. It simply sits there, "
            "yellow and patient, until I hear myself say the sentence that "
            "explains everything."
        ),
    ),
    TextItem(
        id="kaffee",
        title="Der Kaffeeautomat",
        lang="de",
        body=(
            "Der Kaffeeautomat im dritten Stock hat ein Eigenleben entwickelt. Er "
            "brüht nur dann guten Kaffee, wenn niemand zusieht, und verschluckt "
            "jede zweite Münze mit einem zufriedenen Brummen. Die Kollegen nennen "
            "ihn respektvoll den Automaten, mit großem A, und niemand traut sich "
            "mehr, ihn zu reparieren."
        ),
    ),
    TextItem(
        id="anleitung",
        title="Die Aufbauanleitung",
        lang="de",
        body=(
            "Die Aufbauanleitung bestand aus vierzehn Bildern ohne ein einziges "
            "Wort. Auf dem ersten lächelte ein Männchen mit einem Schraubenzieher, "
            "auf dem letzten lächelte es noch immer, obwohl inzwischen drei "
            "Schrauben übrig waren. Zwischen diesen beiden Bildern lag ein "
            "Nachmittag, den niemand jemals vollständig rekonstruieren konnte, und "
            "ein Regal, das seitdem leicht nach links neigt."
        ),
    ),
]


def by_id(text_id: str) -> Optional[TextItem]:
    for item in TEXTS:
        if item.id == text_id:
            return item
    return None


def normalize(raw: str) -> str:
    """Beliebigen Text in eine tippbare Zeile verwandeln."""
    text = raw.replace(" ", " ").replace("\t", " ")
    # Typografische Zeichen, die auf keiner Tastatur bequem liegen, entschärfen.
    for fancy, plain in (("‘", "'"), ("’", "'"), ("“", '"'),
                         ("”", '"'), ("–", "-"), ("—", "-"),
                         ("…", "...")):
        text = text.replace(fancy, plain)
    return re.sub(r"\s+", " ", text).strip()


def from_file(path: str) -> TextItem:
    with open(path, "r", encoding="utf-8") as handle:
        body = normalize(handle.read())
    if not body:
        raise ValueError("Die Datei enthält keinen tippbaren Text.")
    digest = hashlib.sha1(body.encode("utf-8")).hexdigest()[:8]
    name = path.rsplit("/", 1)[-1]
    return TextItem(id="file:" + digest, title=name, lang="?", body=body)
