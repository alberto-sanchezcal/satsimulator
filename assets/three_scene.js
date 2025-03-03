function initThreeScene(sphereTrajectoryData, TimeStep, sunData) {
    const container = document.getElementById('threejs-container');
    const errorLog = document.getElementById('error-log');

    let scene, camera, renderer, labelRenderer, controls, raycaster, mouse, sunLight, sunMat, ambientLight;
    let previousIntersected = null;  
    let spheres = [];  
    let trajectories = [];  
    let sunTrajectory = [];
    let labels = [];
    let currentStep = 0;  
    let maxSteps = 0;  
    let animationStartTime = null; 
    const stepDuration = TimeStep; 

    const EARTH_ROTATION_RATE = 360.9856123035484 /180 * Math.PI/(24*60*60); 
    const Earth_rot_at_J2000 = 280.46/180 * Math.PI;
    let earth, initialEarthRotation;

    let isPlaying = true;
    let speedMultiplier = 1;
    let lastTimestamp = 0;
    let accumulatedTime = 0;  

            
    function clearScene() {
        if (scene) {
            while(scene.children.length > 0){ 
                scene.remove(scene.children[0]); 
            }
        }

        const css2DObjects = document.querySelectorAll('.axis-label');
        css2DObjects.forEach(obj => obj.remove());

        spheres = [];
        trajectories = [];
        sunTrajectory = [];
        labels = [];
    } 
    
    function calculateInitialEarthRotation(epoch) {
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


    function initScene() {
        if (!scene) {
            scene = new THREE.Scene();
        } else {
            clearScene();
        }

        if (!camera) {
            camera = new THREE.PerspectiveCamera(75, container.clientWidth / container.clientHeight, 0.1, 200000000);
            camera.position.set(10000, 10000, 10000);
            camera.up.set(0, 0, 1);
            camera.lookAt(0, 0, 0);
        }

        if (!renderer) {
            renderer = new THREE.WebGLRenderer({ antialias: true });
            renderer.setSize(container.clientWidth, container.clientHeight);
            renderer.shadowMap.enabled = true;

            container.innerHTML = '';
            container.appendChild(renderer.domElement);
        }

        if (!labelRenderer) {
            labelRenderer = new CSS2DRenderer();
            labelRenderer.setSize(container.clientWidth, container.clientHeight);
            labelRenderer.domElement.style.position = 'absolute';
            labelRenderer.domElement.style.top = '0';
            container.appendChild(labelRenderer.domElement);
        }    

        controls = new OrbitControls(camera, labelRenderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.25;
        controls.screenSpacePanning = false;
        controls.maxDistance = 100000;
        controls.minDistance = 6500;

        raycaster = new THREE.Raycaster();
        mouse = new THREE.Vector2();

        container.addEventListener('mousemove', onMouseMove, false);
        container.addEventListener('click', onMouseClick, false);

        window.addEventListener('resize', handleResize, false);

        ambientLight = new THREE.AmbientLight(0xffffff, 0.1); 
        scene.add(ambientLight);

        const earthGeometry = new THREE.SphereGeometry(6371, 64, 64);
        const textureLoader = new THREE.TextureLoader();
        textureLoader.load(
            'https://threejs.org/examples/textures/planets/earth_atmos_2048.jpg',
            (texture) => {
                const earthMaterial = new THREE.MeshPhongMaterial({ map: texture });
                earth = new THREE.Mesh(earthGeometry, earthMaterial);
                earth.castShadow = true;
                earth.rotation.x = Math.PI / 2;
                initialEarthRotation = sunData && sunData.epochs && sunData.epochs.length > 0
                ? calculateInitialEarthRotation(sunData.epochs[0])
                : 0;
                earth.rotation.y = initialEarthRotation;
                scene.add(earth);
            },
        );

        addAxes();

        initAnimation();
    }

    function plotSpheres(sphereTrajectoryData) {
        const sphereGeometry = new THREE.BufferGeometry();
        const color = new THREE.Color();

        sunLight = new THREE.DirectionalLight(0xffffff, 1.5);
        sunLight = new THREE.DirectionalLight(0xffffff, 1.5);
        sunLight.castShadow = true;
        sunLight.shadow.mapSize.width = 2048; 
        sunLight.shadow.mapSize.height = 2048;
        sunLight.shadow.camera.near = 145000000;
        sunLight.shadow.camera.far = 155000000; 
        const d = 100000;
        sunLight.shadow.camera.left = -d;
        sunLight.shadow.camera.right = d;
        sunLight.shadow.camera.top = d;
        sunLight.shadow.camera.bottom = -d;
        
        scene.add(sunLight);

        if (sunData && sunData.coords && sunData.coords.length > 0) {
            const initialSunPosition = sunData.coords[0];
            sunLight.position.set(initialSunPosition[0], initialSunPosition[1], initialSunPosition[2]);
            sunTrajectory = sunData.coords;
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

            material = new THREE.MeshStandardMaterial({
                color: color
            });

            const sphere = new THREE.Mesh(geometry, material);
            sphere.receiveShadow = true;
            const initialPosition = data.coords[0];
            sphere.position.set(initialPosition[0], initialPosition[1], initialPosition[2]);

            scene.add(sphere);
            spheres.push(sphere);

            trajectories.push(data.coords);

            // Only create axis systems if OBJECT_ID is 'CREATED BY USER'
            if (data.OBJECT_ID === 'CREATED BY USER') {
                const orbitAxisSystem = createAxisSystem(0xEC00EC, 'O', false);
                orbitAxisSystem.visible = false;
                sphere.add(orbitAxisSystem);
                sphere.userData.orbitAxisSystem = orbitAxisSystem;

                const bodyAxisSystem = createAxisSystem(0x00D9D9, 'B', true);
                bodyAxisSystem.visible = false;
                sphere.add(bodyAxisSystem);
                sphere.userData.bodyAxisSystem = bodyAxisSystem;
            }
        });

    requestAnimationFrame(updateSpherePositions);
    }

    function plotTrajectory(trajectoryData) {
        const material = new THREE.LineBasicMaterial({ color: 0xffffff });
        const points = trajectoryData.map(coord => new THREE.Vector3(coord[0], coord[1], coord[2]));
        const geometry = new THREE.BufferGeometry().setFromPoints(points);
        const line = new THREE.Line(geometry, material);
        scene.add(line);
        return line;
    }        

    function addAxes() {
        const axesLength = 7500;
        const axesWidth = 10;

        // X-axis (red)
        const xAxisMaterial = new THREE.LineBasicMaterial({ color: 0xff0000, linewidth: axesWidth });
        const xAxisGeometry = new THREE.BufferGeometry().setFromPoints([
            new THREE.Vector3(0, 0, 0),
            new THREE.Vector3(axesLength, 0, 0)
        ]);
        const xAxis = new THREE.Line(xAxisGeometry, xAxisMaterial);
        scene.add(xAxis);

        // Y-axis (green)
        const yAxisMaterial = new THREE.LineBasicMaterial({ color: 0x00ff00, linewidth: axesWidth });
        const yAxisGeometry = new THREE.BufferGeometry().setFromPoints([
            new THREE.Vector3(0, 0, 0),
            new THREE.Vector3(0, axesLength, 0)
        ]);
        const yAxis = new THREE.Line(yAxisGeometry, yAxisMaterial);
        scene.add(yAxis);

        // Z-axis (blue)
        const zAxisMaterial = new THREE.LineBasicMaterial({ color: 0x0000ff, linewidth: axesWidth });
        const zAxisGeometry = new THREE.BufferGeometry().setFromPoints([
            new THREE.Vector3(0, 0, 0),
            new THREE.Vector3(0, 0, axesLength)
        ]);
        const zAxis = new THREE.Line(zAxisGeometry, zAxisMaterial);
        scene.add(zAxis);
    }

    function createAxisSystem(color, prefix, isBodyAxis = false) {
        const axisLength = isBodyAxis ? 250 : 500; // Body axis is half the size of orbital axis
        const axisGroup = new THREE.Group();
        axisGroup.userData.axisLength = axisLength;

        const axes = [
            { dir: new THREE.Vector3(1, 0, 0), label: 'X' },
            { dir: new THREE.Vector3(0, 1, 0), label: 'Y' },
            { dir: new THREE.Vector3(0, 0, 1), label: 'Z' }
        ];

        axes.forEach(({ dir, label }) => {
            const arrow = new THREE.ArrowHelper(dir, new THREE.Vector3(0, 0, 0), axisLength, color);
            axisGroup.add(arrow);

            // Create label
            const labelDiv = document.createElement('div');
            labelDiv.className = 'axis-label';
            labelDiv.textContent = `${label}_${prefix}`;
            labelDiv.style.color = 'white';
            labelDiv.style.fontSize = '7px';
            labelDiv.style.fontFamily = 'Arial, sans-serif';
            labelDiv.style.pointerEvents = 'none';

            const labelObject = new CSS2DObject(labelDiv);
            labelObject.position.copy(dir.multiplyScalar(axisLength));
            axisGroup.add(labelObject);
        });

        return axisGroup;
    }

    function updateAxisLabelsVisibility(sphere, camera) {
        const distanceThreshold = 3000; 
        const distance = sphere.position.distanceTo(camera.position);
        const showAxes = document.getElementById('axis-checkbox').checked;

        if (sphere.userData.orbitAxisSystem) {
            sphere.userData.orbitAxisSystem.children.forEach(child => {
                if (child instanceof CSS2DObject) {
                    child.visible = showAxes && (distance < distanceThreshold);
                }
            });
        }

        if (sphere.userData.bodyAxisSystem) {
            sphere.userData.bodyAxisSystem.children.forEach(child => {
                if (child instanceof CSS2DObject) {
                    child.visible = showAxes && (distance < distanceThreshold);
                }
            });
        }
    }

    function addControls() {
        const controlsDiv = document.createElement('div');
        controlsDiv.id = 'animation-controls';
        controlsDiv.style.position = 'absolute'; // Change to relative as we use flexbox for centering
        controlsDiv.style.width = 'calc(100% - 60px)'; // Account for padding, adjust width if needed
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
            <button id="play-pause" style="
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
            ">Pause</button>
            <input type="range" id="speed-slider" min="1" max="100" step="1" value="1" style="
                -webkit-appearance: none;
                width: 100px;
                height: 5px;
                background: #ddd;
                border-radius: 5px;
                outline: none;
                opacity: 0.7;
                transition: opacity 0.2s;
            " onmouseover="this.style.opacity=1" onmouseout="this.style.opacity=0.7">
            <span id="speed-value" style="
                font-size: 14px;
                width: 25px;
                margin-left: 5px;
                margin-right: 20px;
            ">1x</span>
            <input type="range" id="progress-slider" min="0" max="100" value="0" style="
                -webkit-appearance: none;
                flex-grow: 1;
                height: 5px;
                background: #ddd;
                border-radius: 5px;
                outline: none;
                opacity: 0.7;
                transition: opacity 0.2s;
            " onmouseover="this.style.opacity=1" onmouseout="this.style.opacity=0.7">
            <span id="current-epoch" style="
                font-size: 14px;
                margin-left: 5px;
            "></span>
        `;
        container.appendChild(controlsDiv);

        const cardContainer = document.createElement('div');
        cardContainer.style.position = 'absolute';
        cardContainer.style.top = '10px';
        cardContainer.style.right = '10px';
        cardContainer.style.backgroundColor = 'rgba(255, 255, 255, 0.8)';
        cardContainer.style.padding = '10px';
        cardContainer.style.borderRadius = '5px';
        cardContainer.style.fontFamily = 'Arial, sans-serif';
        cardContainer.style.fontSize = '14px';
        cardContainer.innerHTML = `
            <label>
                <input type="checkbox" id="magnify-checkbox"> Magnify size
            </label>
            <label>
                <input type="checkbox" id="axis-checkbox"> Show Axes
            </label>
        `;
        container.appendChild(cardContainer);

    }

    function setupControlListeners() {
        const magnifyCheckbox = document.getElementById('magnify-checkbox');
        const axisCheckbox = document.getElementById('axis-checkbox');
        const playPauseButton = document.getElementById('play-pause');
        const speedSlider = document.getElementById('speed-slider');
        const progressSlider = document.getElementById('progress-slider');

        magnifyCheckbox.addEventListener('change', (event) => {
            const isMagnified = event.target.checked;
            spheres.forEach((sphere, index) => {
                const data = sphereTrajectoryData[index];
                if (isMagnified) {
                    sphere.scale.set(20000, 20000, 20000);
                    if (sphere.userData.orbitAxisSystem) {
                        sphere.userData.orbitAxisSystem.scale.set(1/20000, 1/20000, 1/20000);
                    }
                    if (sphere.userData.bodyAxisSystem) {
                        sphere.userData.bodyAxisSystem.scale.set(1/20000, 1/20000, 1/20000);
                    }
                }else{
                    sphere.scale.set(1, 1, 1);
                    if (sphere.userData.orbitAxisSystem) {
                        sphere.userData.orbitAxisSystem.scale.set(1, 1, 1);
                    }
                    if (sphere.userData.bodyAxisSystem) {
                        sphere.userData.bodyAxisSystem.scale.set(1, 1, 1);
                    }                    
                }
            });
        });   

        axisCheckbox.addEventListener('change', (event) => {
            const showAxes = event.target.checked;
            spheres.forEach((sphere) => {
                if (sphere.userData.orbitAxisSystem) {
                    sphere.userData.orbitAxisSystem.visible = showAxes;
                }
                if (sphere.userData.bodyAxisSystem) {
                    sphere.userData.bodyAxisSystem.visible = showAxes;
                }
            });
        });          

        playPauseButton.addEventListener('click', () => {
            isPlaying = !isPlaying;
            playPauseButton.textContent = isPlaying ? 'Pause' : 'Play';
            if (isPlaying) {
                lastTimestamp = performance.now();
            }
        });

        speedSlider.addEventListener('input', (event) => {
            const newSpeedMultiplier = parseFloat(event.target.value);
            accumulatedTime += (performance.now() - lastTimestamp) * speedMultiplier;
            lastTimestamp = performance.now();
            speedMultiplier = newSpeedMultiplier;
            document.getElementById('speed-value').textContent = `${speedMultiplier.toFixed(1)}x`;
        });

        progressSlider.addEventListener('input', (event) => {
            currentStep = Math.floor((event.target.value / 100) * maxSteps);
            accumulatedTime = currentStep * stepDuration;
            lastTimestamp = performance.now();
            updateSpherePositions(lastTimestamp);
        });
    }

    function onMouseMove(event) {
        const rect = container.getBoundingClientRect();

        mouse.x = ((event.clientX - rect.left) / container.clientWidth) * 2 - 1;
        mouse.y = -((event.clientY - rect.top) / container.clientHeight) * 2 + 1;

        raycaster.setFromCamera(mouse, camera);

        const intersects = raycaster.intersectObjects(spheres);

        if (intersects.length > 0) {
            const intersected = intersects[0].object;
            const sphereIndex = spheres.indexOf(intersected);

            if (!intersected.userData.label) {
                const labelDiv = document.createElement('div');
                labelDiv.className = 'satellite-label';
                labelDiv.textContent = sphereTrajectoryData[spheres.indexOf(intersected)].OBJECT_NAME;
                labelDiv.style.backgroundColor = 'rgba(0, 0, 0, 0.6)';
                labelDiv.style.color = 'white';
                labelDiv.style.padding = '2px 2px';
                labelDiv.style.borderRadius = '3px';
                labelDiv.style.fontSize = '10px';
                labelDiv.style.fontFamily = 'Arial, sans-serif';
                labelDiv.style.pointerEvents = 'none';

                const label = new CSS2DObject(labelDiv);
                label.position.copy(intersected.position);
                label.center.set(1, 0);
                scene.add(label);
                intersected.userData.label = label;
            }                                
            intersected.userData.label.visible = true;
            // Plot trajectory if not already plotted
            if (!intersected.userData.trajectory) {
                intersected.userData.trajectory = plotTrajectory(trajectories[sphereIndex]);
            }
            //Logic to change the color to white if hovered
            if (previousIntersected && previousIntersected !== intersected) {
                previousIntersected.material.color.set(previousIntersected.currentColor);
                previousIntersected = null; // Reset previous intersected
            }
            if (previousIntersected !== intersected) {
                intersected.currentColor = intersected.material.color.getHex();
                intersected.material.color.set(0xffffff);
                previousIntersected = intersected;
            }

        } else if (previousIntersected) {
            // Hide label if no longer hovered
            if (previousIntersected.userData.label) {
                previousIntersected.userData.label.visible = false;
            }
            // Remove trajectory if no longer hovered
            if (previousIntersected.userData.trajectory) {
                scene.remove(previousIntersected.userData.trajectory);
                previousIntersected.userData.trajectory = null;
            }
            // Restore color of previously intersected sphere if no longer hovered
            previousIntersected.material.color.set(previousIntersected.currentColor);
            previousIntersected = null;
        }
    }

    function onMouseClick(event) {
        const rect = container.getBoundingClientRect();

        // Calculate mouse position in normalized device coordinates
        mouse.x = ((event.clientX - rect.left) / container.clientWidth) * 2 - 1;
        mouse.y = -((event.clientY - rect.top) / container.clientHeight) * 2 + 1;

        // Update the picking ray with the camera and mouse position
        raycaster.setFromCamera(mouse, camera);

        // Calculate objects intersecting the picking ray
        const intersects = raycaster.intersectObjects(spheres);

        if (intersects.length > 0) {
            const point = intersects[0].object.position;
            console.log('Clicked sphere center coordinates:', point.x, point.y, point.z);
        }
    }

    function handleResize() {
        // Update camera aspect ratio and renderer size
        const width = container.clientWidth;
        const height = container.clientHeight;
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
        renderer.setSize(width, height);
        labelRenderer.setSize(width, height);
    }

    function initAnimation() {

        function animate(timestamp) {
            requestAnimationFrame(animate);
            if (controls) controls.update();

            spheres.forEach(sphere => {
                updateAxisLabelsVisibility(sphere, camera);
            });


            if (renderer && scene && camera) {
                renderer.render(scene, camera);
                labelRenderer.render(scene, camera);
            }
        }
        animate();
    }

    function updateAxisSystem(axisSystem, currentAxisData, nextAxisData, t) {
        const axisLength = axisSystem.userData.axisLength;

        for (let i = 0; i < 3; i++) {
            const currentAxis = new THREE.Vector3(...currentAxisData[i]);
            const nextAxis = new THREE.Vector3(...nextAxisData[i]);
            const interpolatedAxis = new THREE.Vector3().lerpVectors(currentAxis, nextAxis, t);
            axisSystem.children[i * 2].setDirection(interpolatedAxis.normalize());
            
            // Update label position
            const labelPosition = interpolatedAxis.normalize().multiplyScalar(axisLength);
            axisSystem.children[i * 2 + 1].position.copy(labelPosition);
        }
    }


    function updateSpherePositions(timestamp) {
        if (!lastTimestamp) {
            lastTimestamp = timestamp;
        }

        if (isPlaying) {
            const deltaTime = timestamp - lastTimestamp;
            accumulatedTime += deltaTime * speedMultiplier;
            lastTimestamp = timestamp;
        }

        currentStep = Math.floor(accumulatedTime / stepDuration);

        if (currentStep >= maxSteps) {
            currentStep = 0;
            accumulatedTime = 0;
            lastTimestamp = timestamp;
        }

        document.getElementById('progress-slider').value = (currentStep / maxSteps) * 100;

        const currentEpoch = sunData.epochs[currentStep];
        document.getElementById('current-epoch').textContent = currentEpoch;

        const t = (accumulatedTime % stepDuration) / stepDuration;

        spheres.forEach((sphere, index) => {
            const trajectory = trajectories[index];
            if (trajectory.length > 0) {
                const currentPositionIndex = currentStep % trajectory.length;
                const nextPositionIndex = (currentStep + 1) % trajectory.length;
                
                const currentPosition = trajectory[currentPositionIndex];
                const nextPosition = trajectory[nextPositionIndex];

                sphere.position.set(
                    currentPosition[0] + (nextPosition[0] - currentPosition[0]) * t,
                    currentPosition[1] + (nextPosition[1] - currentPosition[1]) * t,
                    currentPosition[2] + (nextPosition[2] - currentPosition[2]) * t
                );

                if (sphere.userData.orbitAxisSystem && sphere.userData.bodyAxisSystem) {
                    const data = sphereTrajectoryData[index];
                    
                    const currentOrbitAxis = data.orbitaxis[currentPositionIndex];
                    const nextOrbitAxis = data.orbitaxis[nextPositionIndex];
                    updateAxisSystem(sphere.userData.orbitAxisSystem, currentOrbitAxis, nextOrbitAxis, t);

                    const currentBodyAxis = data.bodyaxis[currentPositionIndex];
                    const nextBodyAxis = data.bodyaxis[nextPositionIndex];
                    updateAxisSystem(sphere.userData.bodyAxisSystem, currentBodyAxis, nextBodyAxis, t);
                }

                if (sphere.userData.label && sphere.userData.label.visible) {
                    sphere.userData.label.position.copy(sphere.position);
                    sphere.userData.label.center.set(1, 0);
                }
            }
        });

        if (earth) {
            const elapsedTime = accumulatedTime / 1000; 
            earth.rotation.y = initialEarthRotation + (elapsedTime * EARTH_ROTATION_RATE);
        }

        if (sunTrajectory.length > 0) {
            const currentSunPositionIndex = currentStep % sunTrajectory.length;
            const nextSunPositionIndex = (currentStep + 1) % sunTrajectory.length;
            
            const currentSunPosition = sunTrajectory[currentSunPositionIndex];
            const nextSunPosition = sunTrajectory[nextSunPositionIndex];

            sunLight.position.set(
                currentSunPosition[0] + (nextSunPosition[0] - currentSunPosition[0]) * t,
                currentSunPosition[1] + (nextSunPosition[1] - currentSunPosition[1]) * t,
                currentSunPosition[2] + (nextSunPosition[2] - currentSunPosition[2]) * t
            );
        }

        requestAnimationFrame(updateSpherePositions);
    }

    initScene();

    if (sphereTrajectoryData && sunData) {
        plotSpheres(sphereTrajectoryData, sunData);
        maxSteps = sunData.epochs.length;
        addControls();
        setupControlListeners();
    }
}