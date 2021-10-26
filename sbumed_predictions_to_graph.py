"""Plugin to create or update RDF file based on model outputs."""

import builtins
import datetime
import functools
import gzip
import hashlib
from os import PathLike
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
from rdflib.namespace import Namespace
from rdflib.namespace import RDF
from rdflib.namespace import XSD

sdo = Namespace("https://schema.org/")
dcmi = Namespace("http://purl.org/dc/terms/")
sbubmi_terms = Namespace("https://bmi.stonybrookmedicine.edu/ns/")
snomed = Namespace("http://snomed.info/id/")
w3_oa = Namespace("http://www.w3.org/ns/oa#")
w3_technical_reports = Namespace("https://www.w3.org/TR/")


class UnknownCellType(Exception):
    pass


class State:
    """Object representing the state of the graph."""

    def __init__(
        self,
        *,
        path: Union[PathLike[str], str],
        creator: str,
        name: str,
        description: str,
        github_url: str,
        slide_path: Optional[Union[PathLike[str], str]] = None,
        slide_md5: Optional[str] = None,
        creator_orcid_id: Optional[str] = None,
        license: Optional[str] = None,
        keywords: Optional[Sequence[str]] = None,
    ):

        self._creator = creator
        self._name = name
        self._description = description
        self._github_url = github_url
        self._slide_path = slide_path
        self._slide_md5 = slide_md5
        self._creator_orcid_id = creator_orcid_id
        self._license = license
        self._keywords = keywords
        self._path = Path(path).resolve()
        self._graph = Graph()

        if not any((self._slide_path, self._slide_md5)):
            raise ValueError("must provide one of slide_path or slide_md5")

        self._add_header()

    def _add_header(self):
        self._graph.bind("schema", sdo)
        if self._slide_md5 is None:
            self._slide_md5 = _md5sum(self._slide_path)
        md5_uriref = URIRef(f"urn:md5:{self._slide_md5}")
        create_action = BNode()
        self._graph.add((create_action, RDF.type, sdo.CreateAction))
        self._graph.add((create_action, sdo.description, Literal(self._description)))
        self._graph.add((create_action, sdo.instrument, URIRef(self._github_url)))
        self._graph.add((create_action, sdo.name, Literal(self._name)))
        self._graph.add((create_action, sdo.object, md5_uriref))
        self._graph.add((create_action, sdo.creator, Literal(self._creator)))
        self._graph.add((create_action, sdo.dateCreated, Literal(_get_timestamp())))
        self._graph.add(
            (create_action, sdo.publisher, URIRef("https://ror.org/01882y777"))
        )
        self._graph.add(
            (create_action, sdo.publisher, URIRef("https://ror.org/05qghxh33"))
        )
        if self._creator_orcid_id is not None:
            self._graph.add((create_action, URIRef(self._creator_orcid_id)))
        if self._license is not None:
            self._graph.add((create_action, sdo.license, Literal(self._license)))
        if self._keywords is not None:
            if any("," in keyword for keyword in self._keywords):
                raise ValueError("keywords may not include commas")
            self._graph.add(
                (create_action, sdo.keywords, Literal(",".join(self._keywords)))
            )
        self._graph.add((create_action, sdo.result, URIRef("")))

    def add(
        self,
        *,
        cell_type: str,
        probability: float,
        polygon_coords: Sequence[Tuple[int, int]],
    ):
        """Add a sample to the state."""
        points = " ".join(f"{x},{y}" for x, y in polygon_coords)
        svg_polygon = f"<polygon points={points} />"
        del points

        uuid_ref = URIRef(f"urn:uuid:{uuid.uuid4().hex}")
        self._graph.add((uuid_ref, RDF.type, w3_oa.Annotation))
        # self._graph.add((uuid_ref, w3_oa.hasBody, _cell_type_to_snomed(cell_type)))

        # Add prediction probability.
        prob_node = BNode()
        self._graph.add((prob_node, RDF.type, _cell_type_to_snomed(cell_type)))
        self._graph.add(
            (
                prob_node,
                URIRef("hal:hasCertainty"),
                Literal(probability, datatype=XSD.float),
            )
        )
        self._graph.add((uuid_ref, w3_oa.hasBody, prob_node))

        # Add polygon.
        polygon_node = BNode()
        self._graph.add((polygon_node, RDF.type, w3_oa.FragmentSelector))
        self._graph.add((polygon_node, RDF.value, Literal(svg_polygon)))
        self._graph.add((polygon_node, dcmi.conformsTo, w3_technical_reports.SVG))
        self._graph.add((uuid_ref, w3_oa.hasSelector, polygon_node))

        self._graph.bind("oa", w3_oa)
        self._graph.bind("dcmi", dcmi)
        self._graph.bind("snomed", snomed)

    def write(self, format="ttl"):
        """Write state of RDF to file."""
        print(f"Writing RDF graph to {self._path}")
        output = self._graph.serialize(destination=None, format=format)
        # Output often has two blank lines at the end. We don't need that.
        output = output.strip() + "\n"
        gz_open = functools.partial(gzip.open, compresslevel=6)
        open_fn = gz_open if self._path.suffix == ".gz" else builtins.open
        with open_fn(self._path, mode="wt") as f:
            f.write(output)


def _get_timestamp() -> str:
    """Get current timestamp in UTC as YYYY-MM-DD HH:MM:SS UTC."""
    dt = datetime.datetime.now(datetime.timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S %Z")


def _md5sum(path: PathLike[str]) -> str:
    """Calculate MD5 hash of a file."""
    md5 = hashlib.md5()
    with open(path, "rb") as f:
        while True:
            data = f.read(1024 * 64)  # 64 kb
            if not data:
                break
            md5.update(data)
    return md5.hexdigest()


def _cell_type_to_snomed(cell_type: str) -> URIRef:
    # Jakub found the terms using https://browser.ihtsdotools.org.
    d = {
        "background": URIRef("urn:jakub:notCell"),  # TODO: change this.
        "lymphocyte": snomed["56972008"],
        "tumor": snomed["252987004"],
        "misc": snomed["49634009"],
    }
    try:
        return d[cell_type.lower()]
    except KeyError:
        msg = (
            f"Got unknown cell type {cell_type}."
            f" Available cell types are {', '.join(d.keys())}."
        )
        raise UnknownCellType(msg)
