<pre>
class AnyGraspTracker(builtins.object)
 |  AnyGraspTracker(config)
 |  
 |  Methods defined here:
 |  
 |  __init__(self, config)
 |      AnyGraspTracker initialization.
 |      
 |      Args:
 |          config: AngGraspTracker config.
 |  
 |  load_net(self)
 |  
 |  update(self, curr_points, curr_colors, prev_grasp_ids=[])
 |  
 |  ----------------------------------------------------------------------
 |  Data descriptors defined here:
 |  
 |  __dict__
 |      dictionary for instance variables
 |  
 |  __weakref__
 |      list of weak references to the object

</pre>

<pre> 
class AnyGrasp(builtins.object)
 |  AnyGrasp(config)
 |  
 |  Methods defined here:
 |  
 |  __init__(self, config)
 |      AnyGrasp initializaiton.
 |      
 |      Args:
 |          config: AnyGrasp config.
 |  
 |  get_grasp(self, points, colors, lims=None, voxel_size=0.005, apply_object_mask=True, dense_grasp=False, collision_detection=True)
 |  
 |  load_net(self)
 |  
 |  parse_preds(self, end_points, apply_object_mask=True)
 |  
 |  ----------------------------------------------------------------------
 |  Data descriptors defined here:
 |  
 |  __dict__
 |      dictionary for instance variables
 |  
 |  __weakref__
 |      list of weak references to the object
</pre>
