function initViewScene(encounterData, sphereTrajectoryData, TimeStep, sunData) {
    const container_view = document.getElementById('3d_camera_sight_sim');

    let scene_view, camera_view, renderer_view, sunLight_view;
    let previousIntersected_view = null;  // Track previously intersected sphere
    let spheres_view = [];  // Store sphere meshes
    let trajectories_view = [];  // Store sphere trajectories
    let sunTrajectory_view = [];
    let currentStep_view;  // Current step in the trajectory
    let maxSteps_view = 0;  // Maximum number of steps in the trajectory
    let animationStartTime_view = null; // Start time for the animation
    const stepDuration = TimeStep; // Duration of each step in milliseconds

    const EARTH_ROTATION_RATE = 360.9856123035484 /180 * Math.PI/(24*60*60); 
    const Earth_rot_at_J2000 = 280.46/180 * Math.PI;
    let earth_view, initialEarthRotation_view;

    let isPlaying_view = false;
    let speedMultiplier_view = 1;
    let lastTimestamp_view = 0;
    let accumulatedTime_view = 0; 
    
    let observantObject;
    let observantTrajectory;
    let observantBodyAxis;

            
    function clearScene_view() {
        if (scene_view) {
            while(scene_view.children.length > 0){ 
                scene_view.remove(scene_view.children[0]); 
            }
        }

        spheres_view = [];
        trajectories_view = [];
        sunTrajectory_view = [];
    }  
    
    function calculateInitialEarthRotation_view(epoch) {
        if (!epoch) {
            return 0; 
        }
        const [datePart, timePart] = epoch.split(' ');
        const [year, month, day] = datePart.split('-').map(Number);
        const [hour, minute, second] = timePart.split(':').map(Number);
        
        const date = new Date(Date.UTC(year, month - 1, day, hour, minute, second));
        const J2000_DATE = new Date(Date.UTC(2000, 0, 1, 12, 0, 0));
        
        const secondsSinceJ2000 = (date.getTime() - J2000_DATE.getTime()) / 1000;
        return secondsSinceJ2000 * EARTH_ROTATION_RATE + Earth_rot_at_J2000;
    }

    function initScene_view(sphereTrajectoryData, encounterData) {
        currentStep_view = encounterData.Index_closest
        observantObject = sphereTrajectoryData.find(item => item.NORAD_CAT_ID === encounterData.NORAD_CAT_ID_observant);
        observantTrajectory = observantObject.coords;
        observantBodyAxis = observantObject.bodyaxis;
        observantSensorWidth = observantObject["Sensor Width"];
        observantSensorHeight = observantObject["Sensor Height"];
        observantCamResolution = observantObject["Camera Resolution"];
        observantFocalLength = observantObject["Focal Length"];
        observantfnumber = observantObject["f-number"];
        

        const horizontalFOV = 2 * Math.atan((observantSensorWidth / 2) / observantFocalLength) * (180 / Math.PI);
        const aspectRatio = observantSensorWidth / observantSensorHeight;

        
        if (!scene_view) {
            scene_view = new THREE.Scene();
        } else {
            clearScene_view();
        }

        if (!camera_view) {
            camera_view = new THREE.PerspectiveCamera(horizontalFOV, aspectRatio, 0.1, 100000);
            const initialPosition_cam_view = observantTrajectory[currentStep_view];
            camera_view.position.set(initialPosition_cam_view[0], initialPosition_cam_view[1], initialPosition_cam_view[2]);

            const initialBodyAxis = observantBodyAxis[currentStep_view];
            const initiallookAtVector = initialBodyAxis[0]
            const lookAtVector = new THREE.Vector3(
                initiallookAtVector[0]*1000 + initialPosition_cam_view[0], 
                initiallookAtVector[1]*1000 + initialPosition_cam_view[1], 
                initiallookAtVector[2]*1000 + initialPosition_cam_view[2]
            );

            const initialupVector = initialBodyAxis[1]
            const upVector  = new THREE.Vector3(-initialupVector[0]*100, -initialupVector[1]*100, -initialupVector[2]*100);
            camera_view.up = upVector;
            camera_view.lookAt(lookAtVector);

        }

        if (!renderer_view) {
            renderer_view = new THREE.WebGLRenderer({ antialias: true });
            renderer_view.setSize(container_view.clientWidth, container_view.clientHeight);
            container_view.innerHTML = '';

            renderer_view.domElement.style.display = 'block';
            renderer_view.domElement.style.margin = 'auto';

            renderer_view.shadowMap.enabled = true;

            container_view.appendChild(renderer_view.domElement);
        }


        window.addEventListener('resize', handleResize_view, false);
        handleResize_view();


        const earthGeometry = new THREE.SphereGeometry(6371, 64, 64);
        const textureLoader = new THREE.TextureLoader();
        textureLoader.load(
            'https://threejs.org/examples/textures/planets/earth_atmos_2048.jpg',
            (texture) => {
                const earthMaterial = new THREE.MeshPhongMaterial({ map: texture });
                earth_view = new THREE.Mesh(earthGeometry, earthMaterial);
                earth_view.castShadow = true;
                earth_view.rotation.x = Math.PI / 2;
                initialEarthRotation_view = sunData && sunData.epochs && sunData.epochs.length > 0
                ? calculateInitialEarthRotation_view(sunData.epochs[0])
                : 0;
                earth_view.rotation.y = initialEarthRotation_view;
                scene.add(earth_view);
            },
        );

        initAnimation_view();
    }

    function plotSpheres_view(sphereTrajectoryData) {
        const sphereGeometry = new THREE.BufferGeometry();
        const color = new THREE.Color();

        sunLight_view = new THREE.DirectionalLight(0xffffff, 1.5);
        sunLight_view = new THREE.DirectionalLight(0xffffff, 1.5);
        sunLight_view.castShadow = true;
        sunLight_view.shadow.mapSize.width = 2048; 
        sunLight_view.shadow.mapSize.height = 2048;
        sunLight_view.shadow.camera.near = 145000000;
        sunLight_view.shadow.camera.far = 155000000; 
        const d = 100000;
        sunLight_view.shadow.camera.left = -d;
        sunLight_view.shadow.camera.right = d;
        sunLight_view.shadow.camera.top = d;
        sunLight_view.shadow.camera.bottom = -d;
        
        scene_view.add(sunLight_view);

        if (sunData && sunData.coords && sunData.coords.length > 0) {
            const initialSunPosition_view = sunData.coords[currentStep_view];
            sunLight_view.position.set(initialSunPosition_view[0], initialSunPosition_view[1], initialSunPosition_view[2]);
            sunTrajectory_view = sunData.coords;
        }

        sphereTrajectoryData.forEach((data, index) => {
            let geometry;
            let material;

            switch (data.shape) {
                case 'sphere':
                    geometry = new THREE.SphereGeometry(data.length / 2, 32, 32);
                    break;
                case 'cyl':
                    geometry = new THREE.CylinderGeometry(data.diameter / 2, data.diameter / 2, data.length, 32);
                    break;
                case 'box':
                    geometry = new THREE.BoxGeometry(data.diameter, data.diameter, data.length);
                    break;
                case 'cone':
                    geometry = new THREE.ConeGeometry(data.diameter / 2, data.length, 32);
                    break;
                default:
                    geometry = new THREE.SphereGeometry(data.length / 2, 32, 32);
                    break;
            }

            switch (data.OBJECT_TYPE) {
                case 'DEBRIS':
                    color.setHex(0xff0000); // Red
                    break;
                case 'PAYLOAD':
                    color.setHex(0x0000ff); // Blue
                    break;
                case 'ROCKET BODY':
                    color.setHex(0xffa500); // Orange
                    break;
                case 'UNKNOWN':
                    color.setHex(0x00ff00); // Green
                    break;
                default:
                    color.setHex(0xffffff); // White
                    break;
            }

            material = new THREE.MeshPhysicalMaterial({
                color: color,
                roughness: 0.4,
                metalness: 1,
                iridescence: 0.6
            });

            const sphere = new THREE.Mesh(geometry, material);
            sphere.receiveShadow = true;
            const initialPosition = data.coords[0];
            sphere.position.set(initialPosition[0], initialPosition[1], initialPosition[2]);

            scene_view.add(sphere);
            spheres_view.push(sphere);

            trajectories_view.push(data.coords);

        });

    requestAnimationFrame(updateSpherePositions_view);
    }
   


    function addControls_view() {
        const controlsDiv = document.createElement('div');
        controlsDiv.id = 'animation-controls-view';
        controlsDiv.style.position = 'absolute'; 
        controlsDiv.style.width = 'calc(100% - 60px)'; 
        controlsDiv.style.bottom = '10px';
        controlsDiv.style.left = '20px';
        controlsDiv.style.backgroundColor = 'rgba(255, 255, 255, 0.7)';
        controlsDiv.style.padding = '10px';
        controlsDiv.style.borderRadius = '5px';
        controlsDiv.style.display = 'flex';
        controlsDiv.style.alignItems = 'center';
        controlsDiv.style.justifyContent = 'center'; 
        controlsDiv.style.fontFamily = 'Arial, sans-serif';
        controlsDiv.innerHTML = `
            <button id="play-pause-view" style="
                background-color: #0384fc;
                border: none;
                color: white;
                padding: 5px;
                text-align: center;
                text-decoration: none;
                display: inline-block;
                font-size: 12px;
                margin-right: 30px;
                width: 50px;
                cursor: pointer;
                border-radius: 5px;
                transition: background-color 0.3s ease;
            ">Play</button>
            <input type="range" id="speed-slider-view" min="1" max="1000" step="1" value="1" style="
                -webkit-appearance: none;
                width: 100px;
                height: 5px;
                background: #ddd;
                border-radius: 5px;
                outline: none;
                opacity: 0.7;
                transition: opacity 0.2s;
            " onmouseover="this.style.opacity=1" onmouseout="this.style.opacity=0.7">
            <span id="speed-value-view" style="
                font-size: 14px;
                width: 25px;
                margin-left: 5px;
                margin-right: 20px;
            ">1x</span>
            <input type="range" id="progress-slider-view" min="0" max="100" value="0" style="
                -webkit-appearance: none;
                flex-grow: 1;
                height: 5px;
                background: #ddd;
                border-radius: 5px;
                outline: none;
                opacity: 0.7;
                transition: opacity 0.2s;
            " onmouseover="this.style.opacity=1" onmouseout="this.style.opacity=0.7">
            <span id="current-epoch-view" style="
                font-size: 14px;
                margin-left: 5px;
            "></span>
        `;
        container_view.appendChild(controlsDiv);

    }

    function setupControlListeners_view() {
        const playPauseButton = document.getElementById('play-pause-view');
        const speedSlider = document.getElementById('speed-slider-view');
        const progressSlider = document.getElementById('progress-slider-view');        

        playPauseButton.addEventListener('click', () => {
            isPlaying_view = !isPlaying_view;
            playPauseButton.textContent = isPlaying_view ? 'Pause' : 'Play';
            if (isPlaying_view) {
                lastTimestamp_view = performance.now();
            }
        });

        speedSlider.addEventListener('input', (event) => {
            const newSpeedMultiplier = parseFloat(event.target.value);
            lastTimestamp_event = performance.now();
            speedMultiplier_event = newSpeedMultiplier;
            document.getElementById('speed-value-view').textContent = `${speedMultiplier_event.toFixed(1)}x`;
        });

        progressSlider.addEventListener('input', (event) => {
            currentStep_view = Math.floor((event.target.value / 100) * maxSteps_view);
            accumulatedTime_view = currentStep_view * stepDuration;
            lastTimestamp_view = performance.now();
            updateSpherePositions_view(lastTimestamp_view);
        });
    }


    function handleResize_view() {
        const containerWidth = container_view.clientWidth;
        const containerHeight = container_view.clientHeight;
        const aspectRatio = camera_view.aspect;
    
        let width, height;
    
        if (containerWidth / containerHeight > aspectRatio) {
            height = containerHeight;
            width = height * aspectRatio;
        } else {
            width = containerWidth;
            height = width / aspectRatio;
        }
    
        camera_view.updateProjectionMatrix();
        renderer_view.setSize(width, height);
        
        renderer_view.domElement.style.position = 'absolute';
        renderer_view.domElement.style.left = '50%';
        renderer_view.domElement.style.top = '50%';
        renderer_view.domElement.style.transform = 'translate(-50%, -43%)';

    }

    function initAnimation_view() {
        function animate_view(timestamp) {
            requestAnimationFrame(animate_view);

            if (renderer_view && scene_view && camera_view) {
                renderer_view.render(scene_view, camera_view);
            }
        }
        animate_view();
    }

    function updateSpherePositions_view(timestamp) {
        if (!lastTimestamp_view) {
            lastTimestamp_view = timestamp;
            accumulatedTime_view = currentStep_view * stepDuration;
        }

        if (isPlaying_view) {
            const deltaTime = timestamp - lastTimestamp_view;
            accumulatedTime_view += deltaTime *speedMultiplier_view;
            lastTimestamp_view = timestamp;
        }

        currentStep_view = Math.floor(accumulatedTime_view / stepDuration);

        if (currentStep_view >= maxSteps_view) {
            currentStep_view = 0;
            accumulatedTime_view = 0;
            lastTimestamp_view = timestamp;
        }

        document.getElementById('progress-slider-view').value = (currentStep_view / maxSteps_view) * 100;

        const currentEpoch = sunData.epochs[currentStep_view];
        document.getElementById('current-epoch-view').textContent = currentEpoch;

        const t = (accumulatedTime_view % stepDuration) / stepDuration;

        spheres_view.forEach((sphere, index) => {
            const trajectory = trajectories_view[index];
            if (trajectory.length > 0) {
                const currentPositionIndex = currentStep_view % trajectory.length;
                const nextPositionIndex = (currentStep_view + 1) % trajectory.length;
                
                const currentPosition = trajectory[currentPositionIndex];
                const nextPosition = trajectory[nextPositionIndex];

                sphere.position.set(
                    currentPosition[0] + (nextPosition[0] - currentPosition[0]) * t,
                    currentPosition[1] + (nextPosition[1] - currentPosition[1]) * t,
                    currentPosition[2] + (nextPosition[2] - currentPosition[2]) * t
                );

                if (sphere.userData.label && sphere.userData.label.visible) {
                    sphere.userData.label.position.copy(sphere.position);
                    sphere.userData.label.center.set(1, 0);
                }
            }
        });

        if (earth_view) {
            const elapsedTime_view = accumulatedTime_view / 1000; 
            earth_view.rotation.y = initialEarthRotation_view + (elapsedTime_view * EARTH_ROTATION_RATE);
        }

        if (sunTrajectory_view.length > 0) {
            const currentSunPositionIndex = currentStep_view % sunTrajectory_view.length;
            const nextSunPositionIndex = (currentStep_view + 1) % sunTrajectory_view.length;
            
            const currentSunPosition = sunTrajectory_view[currentSunPositionIndex];
            const nextSunPosition = sunTrajectory_view[nextSunPositionIndex];

            sunLight_view.position.set(
                currentSunPosition[0] + (nextSunPosition[0] - currentSunPosition[0]) * t,
                currentSunPosition[1] + (nextSunPosition[1] - currentSunPosition[1]) * t,
                currentSunPosition[2] + (nextSunPosition[2] - currentSunPosition[2]) * t
            );
        }

        if (observantTrajectory && observantTrajectory.length > 0 && observantBodyAxis && observantBodyAxis.length > 0)  {
            const currentPositionIndex = currentStep_view % observantTrajectory.length;
            const nextPositionIndex = (currentStep_view + 1) % observantTrajectory.length;
            
            const currentPosition = observantTrajectory[currentPositionIndex];
            const nextPosition = observantTrajectory[nextPositionIndex];

            camera_view.position.set(
                currentPosition[0] + (nextPosition[0] - currentPosition[0]) * t,
                currentPosition[1] + (nextPosition[1] - currentPosition[1]) * t,
                currentPosition[2] + (nextPosition[2] - currentPosition[2]) * t
            );

            const currentBodyAxis = observantBodyAxis[currentPositionIndex];
            const nextBodyAxis = observantBodyAxis[nextPositionIndex];

            const currentlookAtVector = currentBodyAxis[0]
            const nextlookAtVector = nextBodyAxis[0]

            const currentUpVector = currentBodyAxis[1]
            const nextUpVector = nextBodyAxis[1]

            const lookAtVector = new THREE.Vector3(
                currentlookAtVector[0] + (nextlookAtVector[0] - currentlookAtVector[0]) * t + currentPosition[0] + (nextPosition[0] - currentPosition[0]) * t,
                currentlookAtVector[1] + (nextlookAtVector[1] - currentlookAtVector[1]) * t + currentPosition[1] + (nextPosition[1] - currentPosition[1]) * t,
                currentlookAtVector[2] + (nextlookAtVector[2] - currentlookAtVector[2]) * t + currentPosition[2] + (nextPosition[2] - currentPosition[2]) * t
            );

            const upVector = new THREE.Vector3(
                -(currentUpVector[0] + (nextUpVector[0] - currentUpVector[0]) * t),
                -(currentUpVector[1] + (nextUpVector[1] - currentUpVector[1]) * t),
                -(currentUpVector[2] + (nextUpVector[2] - currentUpVector[2]) * t)
            );

            camera_view.lookAt(lookAtVector);
            camera_view.up = (upVector);            

        }        

        requestAnimationFrame(updateSpherePositions_view);
    }

    
    if (sphereTrajectoryData && sunData && encounterData) {
        initScene_view(sphereTrajectoryData, encounterData);
        plotSpheres_view(sphereTrajectoryData, sunData);
        maxSteps_view = sunData.epochs.length;
        addControls_view();
        setupControlListeners_view();

        const initialProgress = (encounterData.Index_closest / maxSteps_view) * 100;
        document.getElementById('progress-slider-view').value = initialProgress;
        
        const initialEpoch = sunData.epochs[encounterData.Index_closest];
        document.getElementById('current-epoch-view').textContent = initialEpoch;                
    }
}