from collections import OrderedDict

import numpy as np

from robosuite.environments.manipulation.manipulation_env import ManipulationEnv
from robosuite.models.arenas import TableArena
from robosuite.models.objects import BoxObject
from robosuite.models.tasks import ManipulationTask
from robosuite.utils.mjcf_utils import CustomMaterial
from robosuite.utils.observables import Observable, sensor
from robosuite.utils.placement_samplers import UniformRandomSampler, SequentialCompositeSampler
from robosuite.utils.transform_utils import convert_quat


class Stack(ManipulationEnv):
    """
    This class corresponds to the stacking task for a single robot arm.

    Args:
        robots (str or list of str): Specification for specific robot arm(s) to be instantiated within this env
            (e.g: "Sawyer" would generate one arm; ["Panda", "Panda", "Sawyer"] would generate three robot arms)
            Note: Must be a single single-arm robot!

        env_configuration (str): Specifies how to position the robots within the environment (default is "default").
            For most single arm environments, this argument has no impact on the robot setup.

        controller_configs (str or list of dict): If set, contains relevant controller parameters for creating a
            custom controller. Else, uses the default controller for this specific task. Should either be single
            dict if same controller is to be used for all robots or else it should be a list of the same length as
            "robots" param

        gripper_types (str or list of str): type of gripper, used to instantiate
            gripper models from gripper factory. Default is "default", which is the default grippers(s) associated
            with the robot(s) the 'robots' specification. None removes the gripper, and any other (valid) model
            overrides the default gripper. Should either be single str if same gripper type is to be used for all
            robots or else it should be a list of the same length as "robots" param

        initialization_noise (dict or list of dict): Dict containing the initialization noise parameters.
            The expected keys and corresponding value types are specified below:

            :`'magnitude'`: The scale factor of uni-variate random noise applied to each of a robot's given initial
                joint positions. Setting this value to `None` or 0.0 results in no noise being applied.
                If "gaussian" type of noise is applied then this magnitude scales the standard deviation applied,
                If "uniform" type of noise is applied then this magnitude sets the bounds of the sampling range
            :`'type'`: Type of noise to apply. Can either specify "gaussian" or "uniform"

            Should either be single dict if same noise value is to be used for all robots or else it should be a
            list of the same length as "robots" param

            :Note: Specifying "default" will automatically use the default noise settings.
                Specifying None will automatically create the required dict with "magnitude" set to 0.0.

        table_full_size (3-tuple): x, y, and z dimensions of the table.

        table_friction (3-tuple): the three mujoco friction parameters for
            the table.

        use_camera_obs (bool): if True, every observation includes rendered image(s)

        use_object_obs (bool): if True, include object (cube) information in
            the observation.

        reward_scale (None or float): Scales the normalized reward function by the amount specified.
            If None, environment reward remains unnormalized

        reward_shaping (bool): if True, use dense rewards.

        placement_initializer (ObjectPositionSampler): if provided, will
            be used to place objects on every reset, else a UniformRandomSampler
            is used by default.

        has_renderer (bool): If true, render the simulation state in
            a viewer instead of headless mode.

        has_offscreen_renderer (bool): True if using off-screen rendering

        render_camera (str): Name of camera to render if `has_renderer` is True. Setting this value to 'None'
            will result in the default angle being applied, which is useful as it can be dragged / panned by
            the user using the mouse

        render_collision_mesh (bool): True if rendering collision meshes in camera. False otherwise.

        render_visual_mesh (bool): True if rendering visual meshes in camera. False otherwise.

        render_gpu_device_id (int): corresponds to the GPU device id to use for offscreen rendering.
            Defaults to -1, in which case the device will be inferred from environment variables
            (GPUS or CUDA_VISIBLE_DEVICES).

        control_freq (float): how many control signals to receive in every second. This sets the amount of
            simulation time that passes between every action input.

        lite_physics (bool): Whether to optimize for mujoco forward and step calls to reduce total simulation overhead.
            Set to False to preserve backward compatibility with datasets collected in robosuite <= 1.4.1.

        horizon (int): Every episode lasts for exactly @horizon timesteps.

        ignore_done (bool): True if never terminating the environment (ignore @horizon).

        hard_reset (bool): If True, re-loads model, sim, and render object upon a reset call, else,
            only calls sim.reset and resets all robosuite-internal variables

        camera_names (str or list of str): name of camera to be rendered. Should either be single str if
            same name is to be used for all cameras' rendering or else it should be a list of cameras to render.

            :Note: At least one camera must be specified if @use_camera_obs is True.

            :Note: To render all robots' cameras of a certain type (e.g.: "robotview" or "eye_in_hand"), use the
                convention "all-{name}" (e.g.: "all-robotview") to automatically render all camera images from each
                robot's camera list).

        camera_heights (int or list of int): height of camera frame. Should either be single int if
            same height is to be used for all cameras' frames or else it should be a list of the same length as
            "camera names" param.

        camera_widths (int or list of int): width of camera frame. Should either be single int if
            same width is to be used for all cameras' frames or else it should be a list of the same length as
            "camera names" param.

        camera_depths (bool or list of bool): True if rendering RGB-D, and RGB otherwise. Should either be single
            bool if same depth setting is to be used for all cameras or else it should be a list of the same length as
            "camera names" param.

        camera_segmentations (None or str or list of str or list of list of str): Camera segmentation(s) to use
            for each camera. Valid options are:

                `None`: no segmentation sensor used
                `'instance'`: segmentation at the class-instance level
                `'class'`: segmentation at the class level
                `'element'`: segmentation at the per-geom level

            If not None, multiple types of segmentations can be specified. A [list of str / str or None] specifies
            [multiple / a single] segmentation(s) to use for all cameras. A list of list of str specifies per-camera
            segmentation setting(s) to use.

    Raises:
        AssertionError: [Invalid number of robots specified]
    """

    def __init__(
        self,
        robots,
        env_configuration="default",
        controller_configs=None,
        gripper_types="default",
        initialization_noise="default",
        table_full_size=(1, 1, 0.05),
        table_friction=(1.0, 5e-3, 1e-4),
        use_camera_obs=True,
        use_object_obs=True,
        reward_scale=1.0,
        reward_shaping=False,
        placement_initializer=None,
        has_renderer=False,
        has_offscreen_renderer=True,
        render_camera="frontview",
        render_collision_mesh=False,
        render_visual_mesh=True,
        render_gpu_device_id=-1,
        control_freq=20,
        lite_physics=True,
        horizon=1000,
        ignore_done=False,
        hard_reset=True,
        camera_names="agentview",
        camera_heights=256,
        camera_widths=256,
        camera_depths=False,
        camera_segmentations=None,  # {None, instance, class, element}
        renderer="mjviewer",
        renderer_config=None,
    ):
        # settings for table top
        self.table_full_size = table_full_size
        self.table_friction = table_friction
        self.table_offset = np.array((0, 0, 0.8))

        # reward configuration
        self.reward_scale = reward_scale
        self.reward_shaping = reward_shaping

        # whether to use ground-truth object states
        self.use_object_obs = use_object_obs

        # object placement initializer
        self.placement_initializer = placement_initializer

        super().__init__(
            robots=robots,
            env_configuration=env_configuration,
            controller_configs=controller_configs,
            base_types="default",
            gripper_types=gripper_types,
            initialization_noise=initialization_noise,
            use_camera_obs=use_camera_obs,
            has_renderer=has_renderer,
            has_offscreen_renderer=has_offscreen_renderer,
            render_camera=render_camera,
            render_collision_mesh=render_collision_mesh,
            render_visual_mesh=render_visual_mesh,
            render_gpu_device_id=render_gpu_device_id,
            control_freq=control_freq,
            lite_physics=lite_physics,
            horizon=horizon,
            ignore_done=ignore_done,
            hard_reset=hard_reset,
            camera_names=camera_names,
            camera_heights=camera_heights,
            camera_widths=camera_widths,
            camera_depths=camera_depths,
            camera_segmentations=camera_segmentations,
            renderer=renderer,
            renderer_config=renderer_config,
        )

    def reward(self, action):
        """
        Reward function for the task.

        Sparse un-normalized reward:

            - a discrete reward of 2.0 is provided if the red block is stacked on the green block

        Un-normalized components if using reward shaping:

            - Reaching: in [0, 0.25], to encourage the arm to reach the cube
            - Grasping: in {0, 0.25}, non-zero if arm is grasping the cube
            - Lifting: in {0, 1}, non-zero if arm has lifted the cube
            - Aligning: in [0, 0.5], encourages aligning one cube over the other
            - Stacking: in {0, 2}, non-zero if cube is stacked on other cube

        The reward is max over the following:

            - Reaching + Grasping
            - Lifting + Aligning
            - Stacking

        The sparse reward only consists of the stacking component.

        Note that the final reward is normalized and scaled by
        reward_scale / 2.0 as well so that the max score is equal to reward_scale

        Args:
            action (np array): [NOT USED]

        Returns:
            float: reward value
        """
        r_reach, r_lift, r_stack = self.staged_rewards()
        if self.reward_shaping:
            reward = max(r_reach, r_lift, r_stack)
        else:
            reward = 2.0 if r_stack > 0 else 0.0

        if self.reward_scale is not None:
            reward *= self.reward_scale / 2.0

        return reward

    def staged_rewards(self):
        """
        Helper function to calculate staged rewards based on current physical states.

        Returns:
            3-tuple:

                - (float): reward for reaching and grasping
                - (float): reward for lifting and aligning
                - (float): reward for stacking
        """
        # reaching is successful when the gripper site is close to the center of the cube
        cubeA_pos = self.sim.data.body_xpos[self.cubeA_body_id]
        cubeB_pos = self.sim.data.body_xpos[self.cubeB_body_id]
        dist = min(
            [
                np.linalg.norm(self.sim.data.site_xpos[self.robots[0].eef_site_id[arm]] - cubeA_pos)
                for arm in self.robots[0].arms
            ]
        )
        r_reach = (1 - np.tanh(10.0 * dist)) * 0.25

        # grasping reward
        grasping_cubeA = self._check_grasp(gripper=self.robots[0].gripper, object_geoms=self.cubeA)
        if grasping_cubeA:
            r_reach += 0.25

        # lifting is successful when the cube is above the table top by a margin
        cubeA_height = cubeA_pos[2]
        table_height = self.table_offset[2]
        cubeA_lifted = cubeA_height > table_height + 0.04
        r_lift = 1.0 if cubeA_lifted else 0.0

        # Aligning is successful when cubeA is right above cubeB
        if cubeA_lifted:
            horiz_dist = np.linalg.norm(np.array(cubeA_pos[:2]) - np.array(cubeB_pos[:2]))
            r_lift += 0.5 * (1 - np.tanh(horiz_dist))

        # stacking is successful when the block is lifted and the gripper is not holding the object
        r_stack = 0
        cubeA_touching_cubeB = self.check_contact(self.cubeA, self.cubeB)
        if not grasping_cubeA and r_lift > 0 and cubeA_touching_cubeB:
            r_stack = 2.0

        return r_reach, r_lift, r_stack

    def _load_model(self):
        """
        Loads an xml model, puts it in self.model
        """
        super()._load_model()

        # Adjust base pose accordingly
        xpos = self.robots[0].robot_model.base_xpos_offset["table"](self.table_full_size[0])
        self.robots[0].robot_model.set_base_xpos(xpos)

        # load model for table top workspace
        mujoco_arena = TableArena(
            table_full_size=self.table_full_size,
            table_friction=self.table_friction,
            table_offset=self.table_offset,
        )

        # Arena always gets set to zero origin
        mujoco_arena.set_origin([0, 0, 0])

        # initialize objects of interest
        tex_attrib = {
            "type": "cube",
        }
        mat_attrib = {
            "texrepeat": "1 1",
            "specular": "0.4",
            "shininess": "0.1",
        }
        redwood = CustomMaterial(
            texture="WoodRed",
            tex_name="redwood",
            mat_name="redwood_mat",
            tex_attrib=tex_attrib,
            mat_attrib=mat_attrib,
        )
        greenwood = CustomMaterial(
            texture="WoodGreen",
            tex_name="greenwood",
            mat_name="greenwood_mat",
            tex_attrib=tex_attrib,
            mat_attrib=mat_attrib,
        )
        self.cubeA = BoxObject(
            name="cubeA",
            size_min=[0.03, 0.03, 0.06],
            size_max=[0.03, 0.03, 0.06],
            rgba=[1, 0, 0, 1],
            material=redwood,
        )
        self.cubeB = BoxObject(
            name="cubeB",
            size_min=[0.02, 0.02, 0.06],
            size_max=[0.02, 0.02, 0.06],
            rgba=[0, 1, 0, 1],
            material=greenwood,
        )
        self.cubeC = BoxObject(
            name="cubeC",
            size_min=[0.02, 0.02, 0.06],
            size_max=[0.02, 0.02, 0.06],
            rgba=[0, 1, 1, 1],
            material=greenwood,
        )
        self.cubeD = BoxObject(
            name="cubeD",
            size_min=[0.02, 0.02, 0.06],
            size_max=[0.02, 0.02, 0.06],
            rgba=[1, 0, 1, 1],
            material=redwood,
        )
        self.cubeE = BoxObject(
            name="cubeE",
            size_min=[0.02, 0.02, 0.06],
            size_max=[0.02, 0.02, 0.06],
            rgba=[1, 1, 0, 1],
            material=redwood,
        )
        self.cubeF = BoxObject(
            name="cubeF",
            size_min=[0.02, 0.02, 0.06],
            size_max=[0.02, 0.02, 0.06],
            rgba=[0, 0, 1, 1],
            material=greenwood,
        )

        cubes = [self.cubeA, self.cubeB, self.cubeC, self.cubeD, self.cubeE, self.cubeF]

        # Create placement initializer
        if self.placement_initializer is not None:
            self.placement_initializer.reset()
            self.placement_initializer.add_objects(cubes)
        else:
            # Perfect horizontal line placement (fixed y value)
            self.placement_initializer = UniformRandomSampler(
                name="ObjectSampler",
                mujoco_objects=cubes,
                x_range=[-0.5, 0.5],
                y_range=[-0.5, 0.5],  # Same min and max for a perfect line
                rotation=None,
                ensure_object_boundary_in_range=False,
                ensure_valid_placement=True,
                reference_pos=self.table_offset,
                z_offset=0.01,
            )

        # task includes arena, robot, and objects of interest
        self.model = ManipulationTask(
            mujoco_arena=mujoco_arena,
            mujoco_robots=[robot.robot_model for robot in self.robots],
            mujoco_objects=cubes,
        )

    def _setup_references(self):
        """
        Sets up references to important components. A reference is typically an
        index or a list of indices that point to the corresponding elements
        in a flatten array, which is how MuJoCo stores physical simulation data.
        """
        super()._setup_references()

        # Additional object references from this env - set up references for all cubes
        self.cubeA_body_id = self.sim.model.body_name2id(self.cubeA.root_body)
        self.cubeB_body_id = self.sim.model.body_name2id(self.cubeB.root_body)
        self.cubeC_body_id = self.sim.model.body_name2id(self.cubeC.root_body)
        self.cubeD_body_id = self.sim.model.body_name2id(self.cubeD.root_body)
        self.cubeE_body_id = self.sim.model.body_name2id(self.cubeE.root_body)
        self.cubeF_body_id = self.sim.model.body_name2id(self.cubeF.root_body)

    def _reset_internal(self):
        """
        Resets simulation internal configurations.
        """
        super()._reset_internal()
        
        # desired (x,y,z) for each cube in world frame:
        fixed = {
            self.cubeA: np.array([-0.5,  0.0, self.table_offset[2] + 0.01]),
            self.cubeB: np.array([-0.3,  0.3, self.table_offset[2] + 0.01]),
            self.cubeC: np.array([ 0.0,  0.1, self.table_offset[2] + 0.01]),
            self.cubeD: np.array([ 0.3, -0.3, self.table_offset[2] + 0.01]),
            self.cubeE: np.array([ 0.4,  0.0, self.table_offset[2] + 0.01]),
            self.cubeF: np.array([-0.3, -0.3, self.table_offset[2] + 0.01]),
        }

        for cube_obj, pos in fixed.items():
            joint_name = cube_obj.joints[0]
            addr = self.sim.model.get_joint_qpos_addr(joint_name)
            if isinstance(addr, tuple):
                start, end = addr
            else:
                start, end = addr, addr + 1
            # build your 7‑D qpos vector (pos + identity quaternion)
            qpos = np.concatenate([pos, np.array([1.0, 0.0, 0.0, 0.0])])
            self.sim.data.qpos[start:end] = qpos

        self.sim.forward()
        
        

    def _setup_observables(self):
        """
        Sets up observables to be used for this environment. Creates object-based observables if enabled
        
        Returns:
            OrderedDict: Dictionary mapping observable names to its corresponding Observable object
        """
        observables = super()._setup_observables()

        # low-level object information
        if self.use_object_obs:
            # define observables modality
            modality = "object"

            # position and rotation of all cubes
            @sensor(modality=modality)
            def cubeA_pos(obs_cache):
                return np.array(self.sim.data.body_xpos[self.cubeA_body_id])

            @sensor(modality=modality)
            def cubeA_quat(obs_cache):
                return convert_quat(np.array(self.sim.data.body_xquat[self.cubeA_body_id]), to="xyzw")

            @sensor(modality=modality)
            def cubeB_pos(obs_cache):
                return np.array(self.sim.data.body_xpos[self.cubeB_body_id])

            @sensor(modality=modality)
            def cubeB_quat(obs_cache):
                return convert_quat(np.array(self.sim.data.body_xquat[self.cubeB_body_id]), to="xyzw")
            
            @sensor(modality=modality)
            def cubeC_pos(obs_cache):
                return np.array(self.sim.data.body_xpos[self.cubeC_body_id])

            @sensor(modality=modality)
            def cubeC_quat(obs_cache):
                return convert_quat(np.array(self.sim.data.body_xquat[self.cubeC_body_id]), to="xyzw")
            
            @sensor(modality=modality)
            def cubeD_pos(obs_cache):
                return np.array(self.sim.data.body_xpos[self.cubeD_body_id])

            @sensor(modality=modality)
            def cubeD_quat(obs_cache):
                return convert_quat(np.array(self.sim.data.body_xquat[self.cubeD_body_id]), to="xyzw")
            
            @sensor(modality=modality)
            def cubeE_pos(obs_cache):
                return np.array(self.sim.data.body_xpos[self.cubeE_body_id])

            @sensor(modality=modality)
            def cubeE_quat(obs_cache):
                return convert_quat(np.array(self.sim.data.body_xquat[self.cubeE_body_id]), to="xyzw")
            
            @sensor(modality=modality)
            def cubeF_pos(obs_cache):
                return np.array(self.sim.data.body_xpos[self.cubeF_body_id])

            @sensor(modality=modality)
            def cubeF_quat(obs_cache):
                return convert_quat(np.array(self.sim.data.body_xquat[self.cubeF_body_id]), to="xyzw")

            # Relative positions between objects
            @sensor(modality=modality)
            def cubeA_to_cubeB(obs_cache):
                return (
                    obs_cache["cubeB_pos"] - obs_cache["cubeA_pos"]
                    if "cubeA_pos" in obs_cache and "cubeB_pos" in obs_cache
                    else np.zeros(3)
                )
            
            @sensor(modality=modality)
            def cubeB_to_cubeC(obs_cache):
                return (
                    obs_cache["cubeC_pos"] - obs_cache["cubeB_pos"]
                    if "cubeB_pos" in obs_cache and "cubeC_pos" in obs_cache
                    else np.zeros(3)
                )
            
            @sensor(modality=modality)
            def cubeC_to_cubeD(obs_cache):
                return (
                    obs_cache["cubeD_pos"] - obs_cache["cubeC_pos"]
                    if "cubeC_pos" in obs_cache and "cubeD_pos" in obs_cache
                    else np.zeros(3)
                )
            
            @sensor(modality=modality)
            def cubeD_to_cubeE(obs_cache):
                return (
                    obs_cache["cubeE_pos"] - obs_cache["cubeD_pos"]
                    if "cubeD_pos" in obs_cache and "cubeE_pos" in obs_cache
                    else np.zeros(3)
                )
            
            @sensor(modality=modality)
            def cubeE_to_cubeF(obs_cache):
                return (
                    obs_cache["cubeF_pos"] - obs_cache["cubeE_pos"]
                    if "cubeE_pos" in obs_cache and "cubeF_pos" in obs_cache
                    else np.zeros(3)
                )

            arm_prefixes = self._get_arm_prefixes(self.robots[0], include_robot_name=False)
            full_prefixes = self._get_arm_prefixes(self.robots[0])

            sensors = [
                cubeA_pos, cubeA_quat, 
                cubeB_pos, cubeB_quat, 
                cubeC_pos, cubeC_quat,
                cubeD_pos, cubeD_quat,
                cubeE_pos, cubeE_quat,
                cubeF_pos, cubeF_quat,
                cubeA_to_cubeB,
                cubeB_to_cubeC,
                cubeC_to_cubeD,
                cubeD_to_cubeE,
                cubeE_to_cubeF
            ]
            
            # Add sensors for distance from end effector to each cube
            sensors += [
                self._get_obj_eef_sensor(full_pf, f"{cube}_pos", f"{arm_pf}gripper_to_{cube}", modality)
                for arm_pf, full_pf in zip(arm_prefixes, full_prefixes)
                for cube in ["cubeA", "cubeB", "cubeC", "cubeD", "cubeE", "cubeF"]
            ]
            
            names = [s.__name__ for s in sensors]

            # Create observables
            for name, s in zip(names, sensors):
                observables[name] = Observable(
                    name=name,
                    sensor=s,
                    sampling_rate=self.control_freq,
                )

        return observables

    def _check_success(self):
        """
        Check if blocks are stacked correctly.

        Returns:
            bool: True if blocks are correctly stacked
        """
        _, _, r_stack = self.staged_rewards()
        return r_stack > 0

    def visualize(self, vis_settings):
        """
        In addition to super call, visualize gripper site proportional to the distance to the cube.

        Args:
            vis_settings (dict): Visualization keywords mapped to T/F, determining whether that specific
                component should be visualized. Should have "grippers" keyword as well as any other relevant
                options specified.
        """
        # Run superclass method first
        super().visualize(vis_settings=vis_settings)

        # Color the gripper visualization site according to its distance to the cube
        if vis_settings["grippers"]:
            self._visualize_gripper_to_target(gripper=self.robots[0].gripper, target=self.cubeA)
