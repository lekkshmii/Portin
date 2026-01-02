import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// Configuration
const CONFIG = {
    globeRadius: 100,
    dotSize: 0.8,
    dotColor: 0x2d3748, // Dark Grey for land
    markerColor: 0x805ad5, // Purple for markers
    bgColor: 0xf0f4f8 // Light pastel background
};

// State
let scene, camera, renderer, controls;
let globeGroup;
let markers = [];
const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2();

// DOM Elements
const container = document.getElementById('canvas-container');
const tooltip = document.getElementById('tooltip');

// Search Elements
const searchInput = document.getElementById('search-input');
const searchResults = document.getElementById('search-results');
let targetRotation = { x: 0, y: 0 };
let isZooming = false;

init();
animate();

function init() {
    // ... (Previous init code) ...
    // 1. Scene Setup
    scene = new THREE.Scene();
    scene.background = new THREE.Color(CONFIG.bgColor);
    scene.fog = new THREE.FogExp2(CONFIG.bgColor, 0.002);

    // 2. Camera
    camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 1000);
    camera.position.z = 300;
    camera.position.y = 50;

    // 3. Renderer
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    container.appendChild(renderer.domElement);

    // 4. Controls
    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.rotateSpeed = 0.5;
    controls.enableZoom = true;
    controls.minDistance = 50; // Allow much closer zoom
    controls.maxDistance = 500;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 0.5;

    // 5. Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);

    const pointLight = new THREE.PointLight(0xffffff, 1);
    pointLight.position.set(200, 200, 200);
    scene.add(pointLight);

    // 6. Create Globe
    createGlobe();

    // 7. Load Data
    loadData();

    // 8. Event Listeners
    window.addEventListener('resize', onWindowResize);
    window.addEventListener('mousemove', onMouseMove);

    // Search Listeners
    searchInput.addEventListener('input', onSearchInput);
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.search-container')) {
            searchResults.classList.add('hidden');
        }
    });
}

// ... (createGlobe and createDots functions remain same) ...

function onSearchInput(e) {
    const query = e.target.value.toLowerCase();
    searchResults.innerHTML = '';

    if (query.length < 1) {
        searchResults.classList.add('hidden');
        return;
    }

    // Filter unique companies from markers
    // Note: markers store data in userData
    const matches = markers.filter(marker =>
        marker.userData.company.toLowerCase().includes(query) ||
        marker.userData.city.toLowerCase().includes(query)
    );

    if (matches.length > 0) {
        searchResults.classList.remove('hidden');
        matches.forEach(marker => {
            const div = document.createElement('div');
            div.className = 'search-item';
            div.textContent = `${marker.userData.company} (${marker.userData.city})`;
            div.onclick = () => zoomToMarker(marker);
            searchResults.appendChild(div);
        });
    } else {
        searchResults.classList.add('hidden');
    }
}

function zoomToMarker(marker) {
    // Stop auto rotation
    controls.autoRotate = false;
    searchResults.classList.add('hidden');
    searchInput.value = marker.userData.company;

    // Calculate target position
    // We want to place the camera in front of the marker
    // The marker is at marker.position
    // We want camera at marker.position * (1 + distance_factor)

    const targetPos = marker.position.clone().normalize().multiplyScalar(CONFIG.globeRadius + 80); // Distance from center

    // Animate Camera
    const startPos = camera.position.clone();
    const startTime = Date.now();
    const duration = 1500; // ms

    function animateZoom() {
        const now = Date.now();
        const progress = Math.min((now - startTime) / duration, 1);

        // Easing function (easeInOutCubic)
        const ease = progress < 0.5 ? 4 * progress * progress * progress : 1 - Math.pow(-2 * progress + 2, 3) / 2;

        camera.position.lerpVectors(startPos, targetPos, ease);
        controls.update();

        if (progress < 1) {
            requestAnimationFrame(animateZoom);
        } else {
            controls.enableDamping = true; // Re-enable damping
        }
    }

    animateZoom();
}

// ... (Rest of the file) ...

function createGlobe() {
    globeGroup = new THREE.Group();
    scene.add(globeGroup);

    // 1. Base Sphere (Dark background)
    const geometry = new THREE.IcosahedronGeometry(CONFIG.globeRadius, 2);
    const material = new THREE.MeshBasicMaterial({
        color: 0xffffff, // White base
        transparent: true,
        opacity: 0.4
    });
    const baseSphere = new THREE.Mesh(geometry, material);
    globeGroup.add(baseSphere);

    // 2. Dotted Map
    // Load image to determine landmasses
    const img = new Image();
    img.crossOrigin = "Anonymous";
    img.onload = () => {
        const canvas = document.createElement('canvas');
        canvas.width = img.width;
        canvas.height = img.height;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0);

        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        createDots(imageData);
    };
    // Use a high-contrast map (black water, white land)
    img.src = 'https://raw.githubusercontent.com/d3/d3-geo/master/test/data/world-110m.json'; // Wait, JSON is not an image.
    // Let's use a reliable image source.
    img.src = 'https://upload.wikimedia.org/wikipedia/commons/thumb/2/23/Blue_Marble_2002.png/1024px-Blue_Marble_2002.png';
    // Actually, let's use a simple visibility map from a stable repo to avoid CORS or complexity.
    // Using a base64 placeholder for a simple map would be safest, but too large.
    // Let's try a standard texture.
    img.src = 'https://raw.githubusercontent.com/mrdoob/three.js/master/examples/textures/planets/earth_specular_2048.jpg';
}

function createDots(imageData) {
    const { width, height, data } = imageData;
    const dots = [];
    const dotDensity = 250; // Increased density for better detail

    // Create a dummy object for positioning
    const dummy = new THREE.Object3D();
    const geometry = new THREE.CircleGeometry(CONFIG.dotSize, 6);
    const material = new THREE.MeshBasicMaterial({ color: CONFIG.dotColor });

    // We'll use InstancedMesh for performance
    // Estimate count first or just use a large buffer? 
    // Let's calculate positions first.

    for (let lat = -90; lat <= 90; lat += 180 / dotDensity) {
        const radius = Math.cos(Math.abs(lat) * Math.PI / 180) * CONFIG.globeRadius;
        const circumference = radius * Math.PI * 2;
        const dotsInRow = circumference / (CONFIG.dotSize * 3); // Tighter spacing

        for (let x = 0; x < dotsInRow; x++) {
            const long = -180 + (x * 360 / dotsInRow);

            // Map Lat/Long to Image Coordinates
            const phi = (90 - lat) * (Math.PI / 180);
            const theta = (180 + long) * (Math.PI / 180);

            // Equirectangular projection mapping
            const u = (long + 180) / 360;
            const v = (lat + 90) / 180;

            const pixelX = Math.floor(u * width);
            const pixelY = Math.floor((1 - v) * height); // Flip Y

            const index = (pixelY * width + pixelX) * 4;
            const brightness = data[index]; // Red channel is enough for grayscale

            // If land (dark in specular map), add dot
            if (brightness < 50) {
                const dot = new THREE.Vector3();
                dot.x = - (CONFIG.globeRadius * Math.sin(phi) * Math.cos(theta));
                dot.z = (CONFIG.globeRadius * Math.sin(phi) * Math.sin(theta));
                dot.y = (CONFIG.globeRadius * Math.cos(phi));
                dots.push(dot);
            }
        }
    }

    const mesh = new THREE.InstancedMesh(geometry, material, dots.length);
    globeGroup.add(mesh);

    dots.forEach((pos, i) => {
        dummy.position.copy(pos);
        // Make the dot face outwards
        const target = new THREE.Vector3().copy(pos).multiplyScalar(2);
        dummy.lookAt(target);
        dummy.updateMatrix();
        mesh.setMatrixAt(i, dummy.matrix);
    });

    mesh.instanceMatrix.needsUpdate = true;
}

async function loadData() {
    try {
        const response = await fetch('data.csv');
        const text = await response.text();
        const rows = text.split('\n').slice(1); // Skip header

        const occupiedPositions = [];

        rows.forEach(row => {
            if (!row.trim()) return;
            // Handle potential commas in quotes if needed, but simple split for now
            const columns = row.split(',');
            if (columns.length < 5) return;

            const company = columns[0];
            let lat = parseFloat(columns[1]);
            let lon = parseFloat(columns[2]);
            const city = columns[3];
            const type = columns[4];

            // Simple collision resolution (Jitter)
            // Check if this position is already taken or very close
            let isOverlapping = true;
            let attempts = 0;

            while (isOverlapping && attempts < 10) {
                isOverlapping = false;
                for (const pos of occupiedPositions) {
                    const dLat = Math.abs(pos.lat - lat);
                    const dLon = Math.abs(pos.lon - lon);
                    if (dLat < 0.5 && dLon < 0.5) {
                        isOverlapping = true;
                        // Add small offset
                        lat += (Math.random() - 0.5) * 1.5;
                        lon += (Math.random() - 0.5) * 1.5;
                        break;
                    }
                }
                attempts++;
            }

            occupiedPositions.push({ lat, lon });
            addMarker(lat, lon, { company, city, type });
        });
    } catch (error) {
        console.error('Error loading data:', error);
    }
}

function addMarker(lat, lon, data) {
    // Convert Lat/Lon to 3D Position
    const phi = (90 - lat) * (Math.PI / 180);
    const theta = (lon + 180) * (Math.PI / 180);

    const x = -(CONFIG.globeRadius * Math.sin(phi) * Math.cos(theta));
    const z = (CONFIG.globeRadius * Math.sin(phi) * Math.sin(theta));
    const y = (CONFIG.globeRadius * Math.cos(phi));

    // Create Marker Mesh
    const geometry = new THREE.SphereGeometry(1.5, 16, 16);
    const material = new THREE.MeshBasicMaterial({ color: CONFIG.markerColor });
    const marker = new THREE.Mesh(geometry, material);

    marker.position.set(x, y, z);
    marker.userData = data; // Store data for tooltip

    globeGroup.add(marker);
    markers.push(marker);
}

function onMouseMove(event) {
    mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
    mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);
    const intersects = raycaster.intersectObjects(markers);

    if (intersects.length > 0) {
        const object = intersects[0].object;
        const data = object.userData;

        tooltip.innerHTML = `<strong>${data.company}</strong>${data.city} (${data.type})`;
        tooltip.style.left = event.clientX + 'px';
        tooltip.style.top = event.clientY + 'px';
        tooltip.classList.remove('hidden');

        document.body.style.cursor = 'pointer';
        controls.autoRotate = false; // Pause rotation on hover
    } else {
        tooltip.classList.add('hidden');
        document.body.style.cursor = 'default';
        controls.autoRotate = true;
    }
}

function onWindowResize() {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
}

function animate() {
    requestAnimationFrame(animate);
    controls.update();

    // Dynamic Marker Scaling
    if (camera && markers.length > 0) {
        const distance = camera.position.distanceTo(new THREE.Vector3(0, 0, 0));
        // Base scale at distance 300 is 1.0
        // As distance gets smaller (zoom in), scale should get smaller
        let scaleFactor = distance / 300;
        scaleFactor = Math.max(0.3, Math.min(scaleFactor, 1.5)); // Clamp scale

        markers.forEach(marker => {
            marker.scale.set(scaleFactor, scaleFactor, scaleFactor);
        });
    }

    renderer.render(scene, camera);
}
