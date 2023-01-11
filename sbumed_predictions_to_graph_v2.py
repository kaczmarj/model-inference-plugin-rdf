"""A newer version of predictions to RDF. Once halcyon nails down a version, we will
not have multiple versions.

This version was made by Jakub to write wsinfer outputs to RDF for upload to Halcyon.
"""

import functools
import gzip
import hashlib
import multiprocessing
from pathlib import Path
from typing import List

import click
import openslide
import pandas as pd
from rdflib import BNode
from rdflib import Graph
from rdflib import Literal
from rdflib import URIRef
from rdflib.namespace import Namespace
from rdflib.namespace import RDF
from rdflib.namespace import XSD
from shapely.geometry import box as _box
import tqdm

dcmi = Namespace("http://purl.org/dc/terms/")
exif = Namespace("http://www.w3.org/2003/12/exif/ns#")
hal = Namespace("https://www.ebremer.com/halcyon/ns/")
sdo = Namespace("https://schema.org/")
w3_oa = Namespace("http://www.w3.org/ns/oa#")


def _get_timestamp() -> str:
    import datetime

    dt = datetime.datetime.now()
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _md5sum(path) -> str:
    """Calculate MD5 hash of a file."""
    md5 = hashlib.md5()
    with open(path, "rb") as f:
        while True:
            data = f.read(1024 * 64)  # 64 kb
            if not data:
                break
            md5.update(data)
    return md5.hexdigest()


class State:
    """State of the plugin.

    Add patch info to the state using `.add_patch()`. Write the output using `.write()`.
    """

    def __init__(
        self,
        slide_path,
        name: str,
        description: str,
        github_url: str,
        orcid_url: str,
        keywords: List[str],
    ):
        slide_path = Path(slide_path)
        if not slide_path.exists():
            raise FileNotFoundError(f"slide not found: {slide_path}")
        self._slide_path = slide_path
        self._slide_md5 = _md5sum(slide_path)
        self._graph = Graph()

        # Add slide dimensions.
        with openslide.open_slide(slide_path) as oslide:
            slide_width, slide_height = oslide.dimensions
        del oslide
        self._slideref = URIRef(f"urn:md5:{self._slide_md5}")
        self._graph.add(
            (self._slideref, exif.height, Literal(slide_height, datatype=XSD.int))
        )
        self._graph.add(
            (self._slideref, exif.width, Literal(slide_width, datatype=XSD.int))
        )

        # Make the CreateAction node.
        create_action = URIRef("https://bmi.stonybrookmedicine.edu/wsinfer/tcga/2023")
        self._graph.add((create_action, RDF.type, sdo.CreateAction))
        self._graph.add((create_action, sdo.name, Literal(name)))
        self._graph.add((create_action, sdo.description, Literal(description)))
        self._graph.add(
            (
                create_action,
                sdo.instrument,
                URIRef(github_url),
            )
        )
        self._graph.add((create_action, sdo.object, self._slideref))
        self._graph.add((create_action, sdo.result, URIRef("")))

        # Make the HalcyonROCrate node.
        rocrate_node = URIRef("")
        self._graph.add((rocrate_node, RDF.type, hal.HalcyonROCrate))
        self._graph.add((rocrate_node, sdo.creator, URIRef(orcid_url)))
        self._graph.add((rocrate_node, sdo.datePublished, Literal(_get_timestamp())))
        self._graph.add((rocrate_node, sdo.description, Literal(description)))
        if keywords is not None:
            for keyword in keywords:
                self._graph.add((rocrate_node, sdo.keywords, Literal(keyword)))
        self._graph.add(
            (
                rocrate_node,
                sdo.license,
                URIRef("https://creativecommons.org/licenses/by-nc-sa/3.0/au/"),
            )
        )
        self._graph.add((rocrate_node, sdo.name, Literal(name)))
        self._graph.add(
            (rocrate_node, sdo.publisher, URIRef("https://ror.org/01882y777"))
        )
        self._graph.add(
            (rocrate_node, sdo.publisher, URIRef("https://ror.org/05qghxh33"))
        )
        self._graph.add((rocrate_node, hal.hasCreateAction, create_action))

        self._graph.bind("hal", hal)
        self._graph.bind("oa", w3_oa)
        self._graph.bind("dcmi", dcmi)
        self._graph.bind("exif", exif)
        self._graph.bind("so", sdo)

    def add_patch(self, *, minx, miny, maxx, maxy, probability: float, classname: str):
        geom = _box(minx=minx, miny=miny, maxx=maxx, maxy=maxy)
        wkt: str = geom.wkt

        probbody_node = BNode()
        self._graph.add((probbody_node, RDF.type, hal.ProbabilityBody))
        self._graph.add(
            (probbody_node, hal.hasCertainty, Literal(probability, datatype=XSD.float))
        )
        self._graph.add(
            (
                probbody_node,
                hal.assertedClass,
                URIRef(f"urn:WSInferLabels:{classname}"),
            )
        )
        fragmentselector_node = BNode()
        self._graph.add((fragmentselector_node, RDF.type, w3_oa.FragmentSelector))
        self._graph.add((fragmentselector_node, RDF.value, Literal(wkt)))
        self._graph.add(
            (
                fragmentselector_node,
                dcmi.conformsTo,
                URIRef("http://www.opengis.net/doc/IS/wkt-crs/1.0"),
            )
        )
        self._graph.add((fragmentselector_node, w3_oa.hasSource, self._slideref))

        parent_node = BNode()
        self._graph.add((parent_node, RDF.type, w3_oa.Annotation))
        self._graph.add((parent_node, w3_oa.hasBody, probbody_node))
        self._graph.add((parent_node, w3_oa.hasSelector, fragmentselector_node))

    def write(self, path, format="ttl"):
        """Write state of RDF to file."""
        path = Path(path)
        print(f"Writing RDF graph to {path}")
        output = self._graph.serialize(destination=None, format=format, encoding=None)
        # Output often has two blank lines at the end. We don't need that.
        output = output.strip() + "\n"
        gz_open = functools.partial(gzip.open, compresslevel=6)
        open_fn = gz_open if path.suffix == ".gz" else open
        with open_fn(path, mode="wt") as f:
            f.write(output)


def _write_one_ttl(
    slide_path: Path,
    *,
    model_results_dir: Path,
    output_dir: Path,
    name: str,
    description: str,
    github_url: str,
    orcid_url: str,
    keywords: List[str],
):
    model_results_csv = model_results_dir / slide_path.with_suffix(".csv").name
    if not model_results_csv.exists():
        print("Model results CSV not found... skipping.")
        print(model_results_csv)
        return
    df = pd.read_csv(model_results_csv)
    output_path = output_dir / slide_path.with_suffix(".ttl.gz").name
    if output_path.exists():
        print("Output TTL exists... skipping.")
        return
    state = State(
        slide_path,
        name=name,
        description=description,
        github_url=github_url,
        orcid_url=orcid_url,
        keywords=keywords,
    )
    cols = [
        col[5:]
        for col in df.filter(like="prob_").columns.tolist()
        if "notumor" not in col
    ]
    for _, row in df.iterrows():
        for col in cols:
            state.add_patch(
                minx=row["minx"],
                miny=row["miny"],
                maxx=row["minx"] + row["width"],
                maxy=row["miny"] + row["height"],
                probability=row[f"prob_{col}"],
                classname=col,
            )
    state.write(output_path)


@click.command()
@click.option(
    "--slide-dir", required=True, type=click.Path(exists=True, path_type=Path)
)
@click.option("--model-results-dir", required=True, type=click.Path(path_type=Path))
@click.option("--output-dir", required=True, type=click.Path(path_type=Path))
@click.option("--name", required=True)
@click.option("--description", required=True)
@click.option("--github-url", required=True)
@click.option("--orcid-url", required=True)
@click.option("--keyword", multiple=True)
@click.option("--num-workers", type=int, default=8)
def main(
    *,
    slide_dir: Path,
    model_results_dir: Path,
    output_dir: Path,
    name: str,
    description: str,
    github_url: str,
    orcid_url: str,
    keyword: List[str],
    num_workers: int,
):
    keywords = keyword
    del keyword
    slide_paths = list(slide_dir.glob("*"))
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError("output directory name exists but is not a directory")
    output_dir.mkdir(exist_ok=True, parents=True)

    _write_one_ttl_single_arg = functools.partial(
        _write_one_ttl,
        model_results_dir=model_results_dir,
        output_dir=output_dir,
        name=name,
        description=description,
        github_url=github_url,
        orcid_url=orcid_url,
        keywords=keywords,
    )

    with multiprocessing.Pool(num_workers) as pool:
        with tqdm.tqdm(total=len(slide_paths)) as pbar:
            for _ in pool.imap_unordered(_write_one_ttl_single_arg, slide_paths):
                pbar.update()


if __name__ == "__main__":
    main()
