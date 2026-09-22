/**
 * Offline trajectory renderer.
 *
 * This mirrors embodied/frontend/robot-scene.js (same background, lights, floor,
 * materials and home camera) so exported media matches what the workbench shows
 * in the browser. Differences: fixed canvas size, explicit synchronous frame
 * stepping instead of OrbitControls + requestAnimationFrame.
 */
import * as THREE from "three";

THREE.Object3D.DEFAULT_UP.set(0, 0, 1);

export class TrajectoryScene {
  constructor({ width = 1280, height = 720, pixelRatio = 2 } = {}) {
    this.width = width;
    this.height = height;
    this.objects = new Map();

    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color("#eef2f1");
    this.camera = new THREE.PerspectiveCamera(36, width / height, 0.01, 20);
    this.camera.up.set(0, 0, 1);

    this.renderer = new THREE.WebGLRenderer({
      antialias: true,
      preserveDrawingBuffer: true,
    });
    this.renderer.setPixelRatio(Math.min(2, pixelRatio));
    // updateStyle must stay on: the canvas is laid out by the flex row, so its
    // CSS size has to follow the requested viewport rather than the backing store.
    this.renderer.setSize(width, height);
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1;

    const hemisphere = new THREE.HemisphereLight(0xffffff, 0xa6b9ad, 1.3);
    hemisphere.position.set(0, 0, 3);
    this.scene.add(hemisphere);

    const light = new THREE.DirectionalLight(0xffffff, 2.2);
    light.position.set(-0.8, -1.1, 2.5);
    light.castShadow = true;
    light.shadow.mapSize.set(1024, 1024);
    Object.assign(light.shadow.camera, {
      left: -1.2,
      right: 1.2,
      top: 1.2,
      bottom: -1.2,
    });
    light.shadow.normalBias = 0.001;
    light.shadow.bias = -0.0001;
    this.scene.add(light);

    const fill = new THREE.DirectionalLight(0xdce9ff, 0.6);
    fill.position.set(1, 1, 1.4);
    this.scene.add(fill);

    const floor = new THREE.Mesh(
      new THREE.PlaneGeometry(200, 200),
      new THREE.MeshStandardMaterial({ color: 0xeef2f1, roughness: 0.93 }),
    );
    floor.position.z = -0.075;
    floor.receiveShadow = true;
    this.scene.add(floor);

    this.robot = new THREE.Group();
    this.scene.add(this.robot);

    this.home = {
      azimuth: -56.8,
      elevation: 27.6,
      distance: 2.24,
      look: new THREE.Vector3(0.32, 0, 0.24),
    };
    this.setCamera();
  }

  /**
   * Spherical camera around a look-at point, matching the workbench home pose
   * (position 1.4 -1.65 1.27, target 0.32 0 0.24) at its default values.
   */
  setCamera({ azimuth = null, elevation = null, distance = null, look = null, fov = null } = {}) {
    if (fov !== null && fov !== this.camera.fov) {
      this.camera.fov = fov;
      this.camera.updateProjectionMatrix();
    }
    const home = this.home;
    const az = THREE.MathUtils.degToRad(azimuth ?? home.azimuth);
    const el = THREE.MathUtils.degToRad(elevation ?? home.elevation);
    const radius = distance ?? home.distance;
    const target = look ? new THREE.Vector3(...look) : home.look.clone();
    const horizontal = Math.cos(el) * radius;
    this.camera.position.set(
      target.x + horizontal * Math.cos(az),
      target.y + horizontal * Math.sin(az),
      target.z + radius * Math.sin(el),
    );
    this.camera.lookAt(target);
    this.camera.updateMatrixWorld();
  }

  load(data) {
    for (const item of data.geometries) {
      let geometry;
      if (item.type === 7) {
        const mesh = data.meshes[item.mesh];
        geometry = new THREE.BufferGeometry();
        geometry.setAttribute(
          "position",
          new THREE.Float32BufferAttribute(mesh.vertices.flat(), 3),
        );
        geometry.setIndex(mesh.faces.flat());
        geometry.computeVertexNormals();
      } else if (item.type === 6) {
        geometry = new THREE.BoxGeometry(...item.size.map((size) => size * 2));
      } else if (item.type === 2) {
        geometry = new THREE.SphereGeometry(item.size[0], 24, 16);
      } else if (item.type === 5) {
        geometry = new THREE.CylinderGeometry(
          item.size[0],
          item.size[0],
          item.size[1] * 2,
          32,
        );
        geometry.rotateX(Math.PI / 2);
      } else continue;
      const [red, green, blue, alpha] = item.color;
      const material = new THREE.MeshStandardMaterial({
        color: new THREE.Color(red, green, blue).convertSRGBToLinear(),
        roughness: item.name === "cube_geom" ? 0.35 : 0.56,
        metalness: 0.08,
        transparent: alpha < 1,
        opacity: alpha,
      });
      const mesh = new THREE.Mesh(geometry, material);
      mesh.castShadow = mesh.receiveShadow = true;
      this.robot.add(mesh);
      this.objects.set(item.id, mesh);
    }
  }

  applyFrame(frame) {
    for (const [id, mesh] of this.objects) {
      const position = frame.positions[id];
      const rotation = frame.rotations[id];
      if (!position || !rotation) continue;
      mesh.position.set(...position);
      mesh.quaternion.setFromRotationMatrix(
        new THREE.Matrix4().set(
          rotation[0], rotation[1], rotation[2], 0,
          rotation[3], rotation[4], rotation[5], 0,
          rotation[6], rotation[7], rotation[8], 0,
          0, 0, 0, 1,
        ),
      );
    }
  }

  draw() {
    this.camera.updateMatrixWorld();
    this.renderer.render(this.scene, this.camera);
  }

  setFrame(frame) {
    this.applyFrame(frame);
    this.draw();
  }
}
