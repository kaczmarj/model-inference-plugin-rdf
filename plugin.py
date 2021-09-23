"""Plugin to create or update RDF file based on model outputs."""

import builtins
import datetime
import gzip
from pathlib import Path
from typing import Optional
from typing import Sequence
from typing import Tuple
from typing import Union
import uuid

from rdflib import BNode
from rdflib import Graph
from rdflib import Literal
from rdflib import URIRef
from rdflib.namespace import RDF
from rdflib.namespace import SDO

uriref_annotation = URIRef("http://www.w3.org/ns/oa/Annotation")
uriref_body = URIRef("http://www.w3.org/ns/oa/body")
uriref_source = URIRef("http://www.w3.org/ns/oa/source")
uriref_target = URIRef("http://www.w3.org/ns/oa/target")
uriref_fragment_selector = URIRef("http://www.w3.org/ns/oa/FragmentSelector")
uriref_selector = URIRef("http://www.w3.org/ns/oa/Selector")
uriref_model_output = URIRef("https://bmi.stonybrookmedicine.edu/ns/modelOutput")


class UnknownCellType(Exception):
    pass


class State:
    """Object representing the state of the graph."""

    def __init__(
        self,
        *,
        path: Union[Path, str],
        creator: str,
        name: str,
        description: str,
        license: Optional[str] = None,
        keywords: Optional[Sequence[str]] = None,
    ) -> "State":

        self._creator = creator
        self._name = name
        self._description = description
        self._license = license
        self._keywords = keywords
        self._path = Path(path).resolve()
        self._graph = Graph()

        # TODO: how to reference self in rdf graph? I don't want this to be Dataset.
        self._graph.bind("schema", SDO)
        us = URIRef("")
        self._graph.add((us, RDF.type, SDO.Dataset))
        self._graph.add((us, SDO.creator, Literal(self._creator)))
        self._graph.add((us, SDO.dateCreated, Literal(_get_timestamp())))
        self._graph.add((us, SDO.description, Literal(self._description)))
        if self._license is not None:
            self._graph.add((us, SDO.license, Literal(self._license)))
        if self._keywords is not None:
            self._graph.add(
                (us, SDO.keywords, Literal('"' + '","'.join(keywords) + '"'))
            )

    def add(
        self,
        *,
        cell_type: str,
        model_probability: float,
        polygon_coords: Sequence[Tuple[int, int]],
        wsi_source: str,
    ) -> "State":
        """Add a sample to the state."""
        # TODO: do we care about the order in which items appear in the RDF file?
        # It seems that the nodes are sorted by uuid.

        points = " ".join(f"{x},{y}" for x, y in polygon_coords)
        svg_polygon = f"<polygon points={points} />"
        del points
        uri_ref_cell_type = URIRef(_cell_type_to_snomed(cell_type))

        target = BNode()
        selection = BNode()
        prob = BNode()
        uuid_ref = URIRef(f"urn:uuid:{uuid.uuid4().hex}")

        self._graph.add((uuid_ref, RDF.type, uriref_annotation))
        self._graph.add((uuid_ref, uriref_body, prob))
        self._graph.add((prob, uriref_model_output, Literal(model_probability)))
        self._graph.add((prob, RDF.type, uri_ref_cell_type))
        self._graph.add((uuid_ref, uriref_target, target))
        self._graph.add((target, RDF.type, uriref_fragment_selector))
        self._graph.add((target, uriref_selector, selection))
        # TODO: add conformsTo
        self._graph.add((selection, RDF.value, Literal(svg_polygon)))
        self._graph.add((target, uriref_source, URIRef(wsi_source)))
        self._graph.bind("oa", URIRef("http://www.w3.org/ns/oa/"))
        self._graph.bind("prob", URIRef("https://bmi.stonybrookmedicine.edu/ns/"))
        return self

    def write(self, format="ttl"):
        """Write state of RDF to file."""
        print(f"Writing to {self._path}")
        output = self._graph.serialize(destination=None, format=format)
        # Output often has two blank lines at the end. We don't need that.
        output = output.strip() + "\n"
        open_fn = gzip.open if self._path.suffix == ".gz" else builtins.open
        with open_fn(self._path, mode="wt") as f:
            f.write(output)


def _get_timestamp() -> str:
    """Get current timestamp in UTC as YYYY-MM-DD HH:MM:SS UTC."""
    dt = datetime.datetime.now(datetime.timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S %Z")


def _cell_type_to_snomed(cell_type: str) -> str:
    d = {
        "lymphocyte": "http://snomed.info/id/fakeIdForLymphocyte",
        "tumor": "http://snomed.info/id/fakeIdForTumor",
        "stroma": "http://snomed.info/id/fakeIdForStroma",
        "misc": "http://snomed.info/id/fakeIdForMisc",
    }
    try:
        return d[cell_type.lower()]
    except KeyError:
        msg = (
            f"Got unknown cell type {cell_type}."
            f" Available cell types are {', '.join(d.keys())}."
        )
        raise UnknownCellType(msg)
