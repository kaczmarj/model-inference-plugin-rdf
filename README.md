# plugin to create rdf file for cell segmentation/classification model outputs

# Example

```python
import sbumed_predictions_to_graph

# Initialize the plugin with metadata.
plugin_state = sbumed_predictions_to_graph.State(
    path="predictions.ttl.gz",
    creator="Jakub Kaczmarzyk",
    name="HoverNet Analysis Pipeline",
    github_url="https://github.com/david-belinsky-sbu/Hovernet_modified/commit/6cd610a32472184d6fbf341cb24902c4180ca3e8",
    slide_path="path/to/slide.svs",
    description="multi-class segmentation using HoverNet",
)

# Add predictions to the state.
plugin_state.add(
    cell_type="lymphocyte",
    probability=0.92,
    polygon_coords=[(24, 50), (10, 10), (20, 4)],
)

# Write the state to disk. This file can be read by viewing software.
plugin_state.write()
```
