function initEventScene(encounterData, sphereTrajectoryData, TimeStep, sunData) {
    const container_event = document.getElementById('event_cam_image');

    let scene_event, camera_event, renderer_event, sunLight_event;
    let previousIntersected_event = null;  // Track previously intersected sphere
    let spheres_event = [];  // Store sphere meshes
    let trajectories_event = [];  // Store sphere trajectories
    let sunTrajectory_event = [];
    let currentStep_event;  // Current step in the trajectory
    let maxSteps_event = 0;  // Maximum number of steps in the trajectory
    let animationStartTime_event = null; // Start time for the animation
    const stepDuration = 1; // Duration of each step in milliseconds

    const EARTH_ROTATION_RATE = 360.9856123035484 /180 * Math.PI/(24*60*60); 
    const Earth_rot_at_J2000 = 280.46/180 * Math.PI;
    let earth_event, initialEarthRotation_event;

    let isPlaying_event = false;
    let speedMultiplier_event = 1;
    let lastTimestamp_event = 0;
    let accumulatedTime_event = 0; 
    
    let observantObject;
    let observantTrajectory;
    let observantBodyAxis;
    let renderWidth;
    let renderHeight;

    let composer, eventCameraPass;
    let previousRenderTarget, currentRenderTarget;
    let lastActiveRenderTarget;


    const EventCameraShader = {
        uniforms: {
            "tDiffuse": { value: null },        // Current rendered frame
            "tPrevious": { value: null },       // Previous rendered frame
            "tPersistence": { value: null },    // Buffer that maintains event data over time
            "tLastActive": { value: null },     // Last active frame (when animation paused)
            "posThreshold": { value: 0.04 },    // Positive brightness change threshold
            "negThreshold": { value: -0.04 },   // Negative brightness change threshold
            "decayRate": { value: 0.01 },       // How quickly events fade away
            "noiseStrength": { value: 0.081 },  // Random noise to simulate sensor noise
            "time": { value: 0 },               // For animating noise
            "isPaused": { value: false }        // Animation state

        },
        vertexShader: `
            varying vec2 vUv;
            void main() {
                vUv = uv;
                gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
            }
        `,
        fragmentShader: `
            uniform sampler2D tDiffuse;
            uniform sampler2D tPrevious;
            uniform sampler2D tPersistence;
            uniform sampler2D tLastActive;
            uniform float posThreshold;  // Positive C value
            uniform float negThreshold;  // Negative C value 
            uniform float decayRate;
            uniform float noiseStrength;
            uniform float time;
            uniform bool isPaused;

            varying vec2 vUv;

            float rand(vec2 co) {
                return fract(sin(dot(co.xy ,vec2(12.9898,78.233))) * 43758.5453);
            }

            // Compute luminance from RGB
            float getLuminance(vec3 color) {
                return dot(color, vec3(0.299, 0.587, 0.114));
            }

            void main() {
                vec4 currentColor = texture2D(tDiffuse, vUv);
                vec4 persistenceColor = texture2D(tPersistence, vUv);
                vec4 previousColor = isPaused ? texture2D(tLastActive, vUv) : texture2D(tPrevious, vUv);
                
                // Get luminance values
                float currentLum = getLuminance(currentColor.rgb);
                float previousLum = getLuminance(previousColor.rgb);
                
                // Add small epsilon to avoid log(0)
                const float epsilon = 0.0001;
                currentLum = max(currentLum, epsilon);
                previousLum = max(previousLum, epsilon);
                
                // Calculate logarithmic intensity difference
                float logDiff = log(currentLum) - log(previousLum);
                
                // Add noise to simulate sensor behavior
                float noise = (rand(vUv + vec2(time)) - 0.5) * noiseStrength;
                logDiff += noise;
                
                // Determine events based on log intensity thresholds
                float charge1 = persistenceColor.r;  // Red channel (positive events)
                float charge3 = persistenceColor.b;  // Blue channel (negative events)
                
                if (logDiff > posThreshold) {
                    charge1 = 1.0;  // Positive event
                    charge3 = 0.0;
                } else if (logDiff < negThreshold) {
                    charge1 = 0.0;
                    charge3 = 1.0;  // Negative event
                } else {
                    charge1 *= (1.0 - decayRate);  // Decay existing events
                    charge3 *= (1.0 - decayRate);
                }
                
                gl_FragColor = vec4(charge1, 0.0, charge3, 1.0);
            }
        `
    };
            
    function clearScene_event() {
        if (scene_event) {
            while(scene_event.children.length > 0){ 
                scene_event.remove(scene_event.children[0]); 
            }
        }

        spheres_event = [];
        trajectories_event = [];
        sunTrajectory_event = [];
    }  
    
    function calculateInitialEarthRotation_event(epoch) {
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

    function initScene_event(sphereTrajectoryData, encounterData) {
        currentStep_event = encounterData.Index_closest
        observantObject = sphereTrajectoryData.find(item => item.NORAD_CAT_ID === encounterData.NORAD_CAT_ID_observant);
        observantTrajectory = observantObject.coords;
        observantBodyAxis = observantObject.bodyaxis;
        observantSensorWidth = observantObject["Sensor Width"];
        observantSensorHeight = observantObject["Sensor Height"];
        observantCamResolution = observantObject["Camera Resolution"]*1000000;
        observantFocalLength = observantObject["Focal Length"];
        observantfnumber = observantObject["f-number"];
        

        const horizontalFOV = 2 * Math.atan((observantSensorWidth / 2) / observantFocalLength) * (180 / Math.PI);
        const aspectRatio = observantSensorWidth / observantSensorHeight;
        renderWidth = Math.round(Math.sqrt(observantCamResolution*aspectRatio));
        renderHeight = Math.round(observantCamResolution/renderWidth);

        
        if (!scene_event) {
            scene_event = new THREE.Scene();
        } else {
            clearScene_event();
        }

        if (!camera_event) {
            camera_event = new THREE.PerspectiveCamera(horizontalFOV, aspectRatio, 0.1, 100000);
            const initialPosition_cam_event = observantTrajectory[currentStep_event];
            camera_event.position.set(initialPosition_cam_event[0], initialPosition_cam_event[1], initialPosition_cam_event[2]);

            const initialBodyAxis = observantBodyAxis[currentStep_event];
            const initiallookAtVector = initialBodyAxis[0]
            const lookAtVector = new THREE.Vector3(
                initiallookAtVector[0]*1000 + initialPosition_cam_event[0], 
                initiallookAtVector[1]*1000 + initialPosition_cam_event[1], 
                initiallookAtVector[2]*1000 + initialPosition_cam_event[2]
            );

            const initialupVector = initialBodyAxis[1]
            const upVector  = new THREE.Vector3(-initialupVector[0]*100, -initialupVector[1]*100, -initialupVector[2]*100);
            camera_event.up = upVector;
            camera_event.lookAt(lookAtVector);

        }

        if (!renderer_event) {
            renderer_event = new THREE.WebGLRenderer({ antialias: true });
            renderer_event.setSize(renderWidth, renderHeight);
            renderer_event.shadowMap.enabled = true;

            container_event.innerHTML = '';

            renderer_event.domElement.style.display = 'block';
            renderer_event.domElement.style.margin = 'auto';

            container_event.appendChild(renderer_event.domElement);

            handleResize_event();
        }
        

        const params = {
            minFilter: THREE.LinearFilter,
            magFilter: THREE.LinearFilter,
            format: THREE.RGBAFormat
        };
        previousRenderTarget = new THREE.WebGLRenderTarget(renderWidth, renderHeight, params);
        currentRenderTarget = new THREE.WebGLRenderTarget(renderWidth, renderHeight, params);
        lastActiveRenderTarget = new THREE.WebGLRenderTarget(renderWidth, renderHeight, params);

    
        composer = new EffectComposer(renderer_event);
        composer.setSize(renderWidth, renderHeight);

        const renderPass = new RenderPass(scene_event, camera_event);
        composer.addPass(renderPass);
    
        eventCameraPass = new ShaderPass(EventCameraShader);
        eventCameraPass.uniforms.tPrevious.value = previousRenderTarget.texture;
        eventCameraPass.uniforms.tLastActive.value = lastActiveRenderTarget.texture;
        composer.addPass(eventCameraPass);        


        window.addEventListener('resize', handleResize_event, false);
        handleResize_event();


        const earthGeometry = new THREE.SphereGeometry(6371, 64, 64);
        const textureLoader = new THREE.TextureLoader();
        textureLoader.load(
            'https://threejs.org/examples/textures/planets/earth_atmos_2048.jpg',
            (texture) => {
                const earthMaterial = new THREE.MeshPhongMaterial({ map: texture });
                earth_event = new THREE.Mesh(earthGeometry, earthMaterial);
                earth_event.castShadow = true;
                earth_event.rotation.x = Math.PI / 2;
                initialEarthRotation_event = sunData && sunData.epochs && sunData.epochs.length > 0
                ? calculateInitialEarthRotation_event(sunData.epochs[0])
                : 0;
                earth_event.rotation.y = initialEarthRotation_event;
                scene.add(earth_event);
            },
        );

        initAnimation_event();
    }

    function plotSpheres_event(sphereTrajectoryData) {
        const sphereGeometry = new THREE.BufferGeometry();
        const color = new THREE.Color();

        sunLight_event = new THREE.DirectionalLight(0xffffff, 1.5);
        sunLight_event = new THREE.DirectionalLight(0xffffff, 1.5);
        sunLight_event.castShadow = true;
        sunLight_event.shadow.mapSize.width = 2048; 
        sunLight_event.shadow.mapSize.height = 2048;
        sunLight_event.shadow.camera.near = 145000000;
        sunLight_event.shadow.camera.far = 155000000; 
        const d = 100000; 
        sunLight_event.shadow.camera.left = -d;
        sunLight_event.shadow.camera.right = d;
        sunLight_event.shadow.camera.top = d;
        sunLight_event.shadow.camera.bottom = -d;
        
        scene_event.add(sunLight_event);

        if (sunData && sunData.coords && sunData.coords.length > 0) {
            const initialSunPosition_event = sunData.coords[currentStep_event];
            sunLight_event.position.set(initialSunPosition_event[0], initialSunPosition_event[1], initialSunPosition_event[2]);
            sunTrajectory_event = sunData.coords;
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

            scene_event.add(sphere);
            spheres_event.push(sphere);

            trajectories_event.push(data.coords);

        });

    requestAnimationFrame(updateSpherePositions_event);
    }
   


    function addControls_event() {
        const controlsDiv = document.createElement('div');
        controlsDiv.id = 'animation-controls-event';
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
            <button id="play-pause-event" style="
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
            <input type="range" id="speed-slider-event" min="1" max="1000" step="1" value="1" style="
                -webkit-appearance: none;
                width: 100px;
                height: 5px;
                background: #ddd;
                border-radius: 5px;
                outline: none;
                opacity: 0.7;
                transition: opacity 0.2s;
            " onmouseover="this.style.opacity=1" onmouseout="this.style.opacity=0.7">
            <span id="speed-value-event" style="
                font-size: 14px;
                width: 25px;
                margin-left: 5px;
                margin-right: 20px;
            ">1x</span>
            <input type="range" id="progress-slider-event" min="0" max="100" value="0" style="
                -webkit-appearance: none;
                flex-grow: 1;
                height: 5px;
                background: #ddd;
                border-radius: 5px;
                outline: none;
                opacity: 0.7;
                transition: opacity 0.2s;
            " onmouseover="this.style.opacity=1" onmouseout="this.style.opacity=0.7">
            <span id="current-epoch-event" style="
                font-size: 14px;
                margin-left: 5px;
            "></span>
        `;
        controlsDiv.innerHTML += `
            <button id="download-image-event" style="
                background-color: #4CAF50;
                border: none;
                color: white;
                padding: 5px;
                text-align: center;
                text-decoration: none;
                display: inline-block;
                font-size: 12px;
                margin-left: 20px;
                cursor: pointer;
                border-radius: 5px;
                transition: background-color 0.3s ease;
            ">Download Image</button>
        `;
        container_event.appendChild(controlsDiv);

    }

    function setupControlListeners_event() {
        const playPauseButton = document.getElementById('play-pause-event');
        const speedSlider = document.getElementById('speed-slider-event');
        const progressSlider = document.getElementById('progress-slider-event');   
        const downloadButton = document.getElementById('download-image-event');
     

        playPauseButton.addEventListener('click', () => {
            isPlaying_event = !isPlaying_event;
            playPauseButton.textContent = isPlaying_event ? 'Pause' : 'Play';
            if (isPlaying_event) {
                lastTimestamp_event = performance.now();
                renderer_event.setRenderTarget(lastActiveRenderTarget);
                renderer_event.render(scene_event, camera_event);
            }
        });

        speedSlider.addEventListener('input', (event) => {
            const newSpeedMultiplier = parseFloat(event.target.value);
            lastTimestamp_event = performance.now();
            speedMultiplier_event = newSpeedMultiplier;
            document.getElementById('speed-value-event').textContent = `${speedMultiplier_event.toFixed(1)}x`;
        });

        progressSlider.addEventListener('input', (event) => {
            currentStep_event = Math.floor((event.target.value / 100) * maxSteps_event);
            accumulatedTime_event = currentStep_event * stepDuration;
            lastTimestamp_event = performance.now();
            updateSpherePositions_event(lastTimestamp_event);
        });

        downloadButton.addEventListener('click', downloadImage_event);

    }



    function handleResize_event() {
        const containerWidth = container_event.clientWidth;
        const containerHeight = container_event.clientHeight;
        const aspectRatio = camera_event.aspect;
    
        let width, height;
    
        if (containerWidth / containerHeight > aspectRatio) {
            height = containerHeight;
            width = height * aspectRatio;
        } else {
            width = containerWidth;
            height = width / aspectRatio;
        }
    
        camera_event.updateProjectionMatrix();
        renderer_event.setSize(renderWidth, renderHeight);

        renderer_event.domElement.style.width = `${width}px`;
        renderer_event.domElement.style.height = `${height}px`;
        renderer_event.domElement.style.position = 'absolute';
        renderer_event.domElement.style.left = '50%';
        renderer_event.domElement.style.top = '50%';
        renderer_event.domElement.style.transform = 'translate(-50%, -43%)';

        if (composer) {
            composer.setSize(renderWidth, renderHeight);
        }
        if (previousRenderTarget && currentRenderTarget) {
            previousRenderTarget.setSize(renderWidth, renderHeight);
            currentRenderTarget.setSize(renderWidth, renderHeight);
        }

    }

    function initAnimation_event() {
        function animate_event(timestamp) {
            requestAnimationFrame(animate_event);
        
            if (renderer_event && scene_event && camera_event) {
                renderer_event.setRenderTarget(currentRenderTarget);
                renderer_event.render(scene_event, camera_event);
        
                eventCameraPass.uniforms.tDiffuse.value = currentRenderTarget.texture;
                eventCameraPass.uniforms.isPaused.value = !isPlaying_event;
                
                if (isPlaying_event) {
                    renderer_event.setRenderTarget(lastActiveRenderTarget);
                    renderer_event.render(scene_event, camera_event);
                    eventCameraPass.uniforms.tLastActive.value = lastActiveRenderTarget.texture;
                }
        
                composer.render();
        
                const temp = previousRenderTarget;
                previousRenderTarget = currentRenderTarget;
                currentRenderTarget = temp;
        
                eventCameraPass.uniforms.tPrevious.value = previousRenderTarget.texture;
            }
        }
        animate_event();
    }

    function updateSpherePositions_event(timestamp) {
        if (!lastTimestamp_event) {
            lastTimestamp_event = timestamp;
            accumulatedTime_event = currentStep_event * stepDuration;
        }

        if (isPlaying_event) {
            const deltaTime = timestamp - lastTimestamp_event;
            accumulatedTime_event += deltaTime * speedMultiplier_event / 1000;
            lastTimestamp_event = timestamp;
        }

        currentStep_event = Math.floor(accumulatedTime_event / stepDuration);

        if (currentStep_event >= maxSteps_event) {
            currentStep_event = 0;
            accumulatedTime_event = 0;
            lastTimestamp_event = timestamp;
        }

        document.getElementById('progress-slider-event').value = (currentStep_event / maxSteps_event) * 100;

        const t = (accumulatedTime_event % stepDuration) / stepDuration;

        const interpolatedEpoch = interpolateEpoch(sunData.epochs, currentStep_event, t);
        document.getElementById('current-epoch-event').textContent = interpolatedEpoch.toISOString();

        spheres_event.forEach((sphere, index) => {
            const trajectory = trajectories_event[index];
            if (trajectory.length > 0) {
                const currentPositionIndex = currentStep_event % trajectory.length;
                const nextPositionIndex = (currentStep_event + 1) % trajectory.length;
                
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

        if (earth_event) {
            const elapsedTime_event = accumulatedTime_event / 1000; 
            earth_event.rotation.y = initialEarthRotation_event + (elapsedTime_event * EARTH_ROTATION_RATE);
        }

        if (sunTrajectory_event.length > 0) {
            const currentSunPositionIndex = currentStep_event % sunTrajectory_event.length;
            const nextSunPositionIndex = (currentStep_event + 1) % sunTrajectory_event.length;
            
            const currentSunPosition = sunTrajectory_event[currentSunPositionIndex];
            const nextSunPosition = sunTrajectory_event[nextSunPositionIndex];

            sunLight_event.position.set(
                currentSunPosition[0] + (nextSunPosition[0] - currentSunPosition[0]) * t,
                currentSunPosition[1] + (nextSunPosition[1] - currentSunPosition[1]) * t,
                currentSunPosition[2] + (nextSunPosition[2] - currentSunPosition[2]) * t
            );
        }

        if (observantTrajectory && observantTrajectory.length > 0 && observantBodyAxis && observantBodyAxis.length > 0)  {
            const currentPositionIndex = currentStep_event % observantTrajectory.length;
            const nextPositionIndex = (currentStep_event + 1) % observantTrajectory.length;
            
            const currentPosition = observantTrajectory[currentPositionIndex];
            const nextPosition = observantTrajectory[nextPositionIndex];

            camera_event.position.set(
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

            camera_event.lookAt(lookAtVector);
            camera_event.up = (upVector);            

        }        

        requestAnimationFrame(updateSpherePositions_event);
    }

    function interpolateEpoch(epochs, currentStep, t) {
        const currentEpoch = new Date(epochs[currentStep]);
        const nextEpoch = new Date(epochs[(currentStep + 1) % epochs.length]);
        const timeDiff = nextEpoch - currentEpoch;
        return new Date(currentEpoch.getTime() + timeDiff * t);
    }

    function downloadImage_event() {
        renderer_event.setRenderTarget(currentRenderTarget);
        renderer_event.render(scene_event, camera_event);
    
        composer.render();
    
        const imageData = renderer_event.domElement.toDataURL('image/png');

        const currentStep = Math.floor(accumulatedTime_event / stepDuration);
        const t = (accumulatedTime_event % stepDuration) / stepDuration;
        const interpolatedEpoch = interpolateEpoch(sunData.epochs, currentStep, t);
        const formattedEpoch = interpolatedEpoch.toISOString().replace(/[:.]/g, '-');
        const filename = `${formattedEpoch}_${encounterData.NORAD_CAT_ID_observant}_${encounterData.NORAD_CAT_ID_observed}.png`;
    
        const link = document.createElement('a');
        link.href = imageData;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    
    if (sphereTrajectoryData && sunData && encounterData) {
        initScene_event(sphereTrajectoryData, encounterData);
        plotSpheres_event(sphereTrajectoryData, sunData);
        maxSteps_event = sunData.epochs.length;
        addControls_event();
        setupControlListeners_event();

        const initialProgress = (encounterData.Index_closest / maxSteps_event) * 100;
        document.getElementById('progress-slider-event').value = initialProgress;
        
        const initialEpoch = sunData.epochs[encounterData.Index_closest];
        document.getElementById('current-epoch-event').textContent = initialEpoch;                
    }
}
