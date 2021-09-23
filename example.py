"""Fake example of running fake inference."""

import plugin

# Initialize the plugin.
plugin_state = plugin.State(
    path="foo.ttl",
    creator="Jakub Kaczmarzyk",
    name="Testing Session",
    description="Useless output from a testing session.",
    license="MIT",
    keywords=["foo", "bar"],
)

# Imagine doing this during model inference with hovernet...
wsi_source = "foo.svs"

# Add an entry with the inference result ...
plugin_state.add(
    cell_type="tumor",
    model_probability=0.84,
    polygon_coords=[(1, 1), (1, 0), (0, 0), (0, 1), (1, 1)],
    wsi_source=wsi_source,
)

# ... multiple times...
plugin_state.add(
    cell_type="lymphocyte",
    model_probability=0.92,
    polygon_coords=[(10, 10), (10, 5), (5, 5), (5, 10), (10, 10)],
    wsi_source=wsi_source,
)

# Save RDF graph to file.
plugin_state.write()
