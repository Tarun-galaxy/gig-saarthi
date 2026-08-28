/**
 * GigMap — Reusable Leaflet map component for Gig Saarthi.
 *
 * Usage:
 *   GigMap.init('map-id', { center: [lat, lon], zoom: 13 });
 *   GigMap.setSearchBox('search-input-id', 'suggestions-container-id');
 *   GigMap.addMarker(id, lat, lon, { icon, popup, draggable });
 *   GigMap.drawRoute(lat1, lon1, lat2, lon2, { onRouteReady });
 *   GigMap.useCurrentLocation({ onLocationFound });
 */

const GigMap = (() => {
    let _map = null;
    let _markers = {};
    let _routeLayer = null;
    let _tileUrl = null;
    let _attribution = null;
    let _searchDebounce = null;

    // Default icon colors
    const ICONS = {
        customer: '#dc2626',
        worker: '#16a34a',
        selected: '#2563eb',
        pin: '#7c3aed',
    };

    function _makeIcon(emoji, color, size = 32) {
        return L.divIcon({
            html: `<div style="
                background:${color};
                width:${size}px;height:${size}px;
                border-radius:50%;
                border:3px solid white;
                box-shadow:0 2px 8px rgba(0,0,0,.35);
                display:flex;align-items:center;justify-content:center;
                font-size:${Math.round(size * 0.45)}px;
                cursor:pointer;
            ">${emoji}</div>`,
            className: '',
            iconSize: [size, size],
            iconAnchor: [size / 2, size / 2],
        });
    }

    /**
     * Initialize the map. Call once per page.
     * @param {string} containerId - DOM id of the map div.
     * @param {object} opts - { center: [lat,lon], zoom, tileUrl, attribution }
     */
    function init(containerId, opts = {}) {
        const center = opts.center || [28.6139, 77.2090]; // Delhi
        const zoom = opts.zoom || 13;

        _tileUrl = opts.tileUrl || 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
        _attribution = opts.attribution || '&copy; OpenStreetMap contributors';

        _map = L.map(containerId, {
            zoomControl: true,
            attributionControl: true,
        }).setView(center, zoom);

        L.tileLayer(_tileUrl, {
            attribution: _attribution,
            maxZoom: 19,
        }).addTo(_map);

        // Invalidate size after a short delay (fixes rendering in hidden/collapsed containers)
        setTimeout(() => _map.invalidateSize(), 200);

        return _map;
    }

    /** Get the underlying Leaflet map instance. */
    function getMap() {
        return _map;
    }

    // ──────────────────────────────────────────
    //  Markers
    // ──────────────────────────────────────────

    /**
     * Add a marker to the map.
     * @param {string} id - Unique key for this marker.
     * @param {number} lat
     * @param {number} lon
     * @param {object} opts - { emoji, color, popup, draggable, size }
     */
    function addMarker(id, lat, lon, opts = {}) {
        if (_markers[id]) {
            _map.removeLayer(_markers[id]);
        }

        const emoji = opts.emoji || '📍';
        const color = opts.color || ICONS.pin;
        const icon = _makeIcon(emoji, color, opts.size || 32);
        const draggable = opts.draggable || false;

        const marker = L.marker([lat, lon], { icon, draggable }).addTo(_map);

        if (opts.popup) {
            marker.bindPopup(opts.popup);
        }
        if (opts.tooltip) {
            marker.bindTooltip(opts.tooltip);
        }

        // Store metadata
        marker._gigId = id;
        marker._gigLat = lat;
        marker._gigLon = lon;

        _markers[id] = marker;
        return marker;
    }

    /** Remove a marker by id. */
    function removeMarker(id) {
        if (_markers[id]) {
            _map.removeLayer(_markers[id]);
            delete _markers[id];
        }
    }

    /** Get a marker by id. */
    function getMarker(id) {
        return _markers[id] || null;
    }

    /** Center map on a marker. */
    function panToMarker(id) {
        if (_markers[id]) {
            _map.setView(_markers[id].getLatLng(), 15);
            _markers[id].openPopup();
        }
    }

    /** Fit map bounds to show all markers. */
    function fitAllMarkers(padding = 40) {
        const layerGroup = L.layerGroup(Object.values(_markers));
        if (layerGroup.getLayers().length > 0) {
            _map.fitBounds(layerGroup.getBounds().pad(0.2), { padding: [padding, padding] });
        }
    }

    // ──────────────────────────────────────────
    //  Current Location
    // ──────────────────────────────────────────

    /**
     * Use browser geolocation → reverse geocode → add pin + fill address.
     * @param {object} opts - { buttonId, searchInputId, addressInputId, latInputId, lonInputId, onLocationFound, onError }
     */
    function useCurrentLocation(opts = {}) {
        const btn = opts.buttonId ? document.getElementById(opts.buttonId) : null;
        let originalBtnHtml = '';
        
        if (btn) {
            originalBtnHtml = btn.innerHTML;
            btn.disabled = true;
            btn.classList.add('opacity-80', 'cursor-wait');
            btn.innerHTML = `
                <svg class="animate-spin -ml-0.5 mr-1.5 h-3.5 w-3.5 text-primary-600 dark:text-primary-400 inline" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <span>Detecting GPS...</span>
            `;
        }

        if (!navigator.geolocation) {
            if (btn) {
                btn.innerHTML = `<span>⚠️ Geolocation not supported</span>`;
                setTimeout(() => { btn.innerHTML = originalBtnHtml; btn.disabled = false; btn.classList.remove('opacity-80', 'cursor-wait'); }, 3000);
            } else {
                alert('Geolocation is not supported by your browser.');
            }
            return;
        }

        navigator.geolocation.getCurrentPosition(
            (pos) => {
                const lat = pos.coords.latitude;
                const lon = pos.coords.longitude;

                // Add/move location marker
                addMarker('my-location', lat, lon, {
                    emoji: '📍',
                    color: ICONS.customer,
                    popup: '<b>Your Location</b>',
                });
                _map.setView([lat, lon], 15);

                // Reverse geocode to fill address
                fetch(`/api/reverse-geocode/?lat=${lat}&lon=${lon}`)
                    .then(r => r.json())
                    .then(data => {
                        if (data.formatted_address) {
                            if (opts.searchInputId && document.getElementById(opts.searchInputId)) {
                                document.getElementById(opts.searchInputId).value = data.formatted_address;
                            }
                            if (opts.addressInputId && document.getElementById(opts.addressInputId)) {
                                document.getElementById(opts.addressInputId).value = data.formatted_address;
                            }
                        }
                    })
                    .catch(() => {});

                // Fill hidden inputs
                if (opts.latInputId && document.getElementById(opts.latInputId)) {
                    document.getElementById(opts.latInputId).value = lat.toFixed(6);
                }
                if (opts.lonInputId && document.getElementById(opts.lonInputId)) {
                    document.getElementById(opts.lonInputId).value = lon.toFixed(6);
                }

                if (btn) {
                    btn.innerHTML = `
                        <span class="inline-flex items-center text-emerald-600 dark:text-emerald-400 font-bold">
                            <span class="mr-1">✓</span> GPS Located
                        </span>
                    `;
                    setTimeout(() => {
                        btn.innerHTML = originalBtnHtml;
                        btn.disabled = false;
                        btn.classList.remove('opacity-80', 'cursor-wait');
                        if (typeof lucide !== 'undefined') lucide.createIcons();
                    }, 2500);
                }

                if (opts.onLocationFound) opts.onLocationFound(lat, lon);
            },
            (err) => {
                if (btn) {
                    btn.innerHTML = `<span class="text-rose-600 dark:text-rose-400 font-bold">⚠️ GPS unavailable</span>`;
                    setTimeout(() => {
                        btn.innerHTML = originalBtnHtml;
                        btn.disabled = false;
                        btn.classList.remove('opacity-80', 'cursor-wait');
                        if (typeof lucide !== 'undefined') lucide.createIcons();
                    }, 3000);
                } else {
                    alert('Unable to get your location: ' + err.message);
                }
                if (opts.onError) opts.onError(err);
            },
            { enableHighAccuracy: true, timeout: 10000 }
        );
    }

    // ──────────────────────────────────────────
    //  Search / Autocomplete
    // ──────────────────────────────────────────

    /**
     * Wire up a search input with Geoapify autocomplete.
     * @param {string} inputId - The search input DOM id.
     * @param {string} suggestionsId - The dropdown container DOM id.
     * @param {object} opts - { onSelect, addressInputId, latInputId, lonInputId, biasLat, biasLon }
     */
    function setSearchBox(inputId, suggestionsId, opts = {}) {
        const input = document.getElementById(inputId);
        const dropdown = document.getElementById(suggestionsId);
        if (!input || !dropdown) return;

        input.addEventListener('input', () => {
            clearTimeout(_searchDebounce);
            const query = input.value.trim();

            if (query.length < 2) {
                dropdown.classList.add('hidden');
                dropdown.innerHTML = '';
                return;
            }

            let url = `/api/autocomplete/?q=${encodeURIComponent(query)}`;
            if (opts.biasLat && opts.biasLon) {
                url += `&bias=${opts.biasLat},${opts.biasLon}`;
            }

            _searchDebounce = setTimeout(() => {
                fetch(url)
                    .then(r => r.json())
                    .then(data => {
                        if (!data.results || data.results.length === 0) {
                            dropdown.classList.add('hidden');
                            return;
                        }

                        dropdown.innerHTML = data.results.map((r, i) => `
                            <div class="px-4 py-2 hover:bg-gray-100 cursor-pointer border-b border-gray-100 last:border-0"
                                 data-index="${i}">
                                <p class="text-sm font-medium text-gray-900">${r.formatted_address}</p>
                                <p class="text-xs text-gray-500">${r.city || ''} ${r.state || ''}</p>
                            </div>
                        `).join('');

                        dropdown.classList.remove('hidden');

                        // Bind click handlers
                        dropdown.querySelectorAll('[data-index]').forEach(el => {
                            el.addEventListener('click', () => {
                                const idx = parseInt(el.dataset.index);
                                const result = data.results[idx];

                                input.value = result.formatted_address;
                                dropdown.classList.add('hidden');

                                // Place marker
                                addMarker('my-location', result.lat, result.lon, {
                                    emoji: '📍',
                                    color: ICONS.customer,
                                    popup: `<b>You</b><br>${result.formatted_address}`,
                                });
                                _map.setView([result.lat, result.lon], 15);

                                // Fill hidden inputs
                                if (opts.addressInputId) {
                                    document.getElementById(opts.addressInputId).value = result.formatted_address;
                                }
                                if (opts.latInputId) {
                                    document.getElementById(opts.latInputId).value = result.lat.toFixed(6);
                                }
                                if (opts.lonInputId) {
                                    document.getElementById(opts.lonInputId).value = result.lon.toFixed(6);
                                }

                                if (opts.onSelect) opts.onSelect(result);
                            });
                        });
                    })
                    .catch(() => {});
            }, 300);
        });

        // Close dropdown on outside click
        document.addEventListener('click', (e) => {
            if (!input.contains(e.target) && !dropdown.contains(e.target)) {
                dropdown.classList.add('hidden');
            }
        });
    }

    // ──────────────────────────────────────────
    //  Routing
    // ──────────────────────────────────────────

    /**
     * Draw a route between two points.
     * Fetches route from our Django API (which calls Geoapify).
     *
     * @param {number} lat1, lon1 - Origin
     * @param {number} lat2, lon2 - Destination
     * @param {object} opts - { mode, color, weight, onRouteReady }
     * @returns {Promise}
     */
    function drawRoute(lat1, lon1, lat2, lon2, opts = {}) {
        // Clear previous route
        if (_routeLayer) {
            _map.removeLayer(_routeLayer);
            _routeLayer = null;
        }

        const mode = opts.mode || 'drive';
        const url = `/api/route/?origin_lat=${lat1}&origin_lon=${lon1}&dest_lat=${lat2}&dest_lon=${lon2}&mode=${mode}`;

        return fetch(url)
            .then(r => r.json())
            .then(data => {
                if (!data.polyline || data.polyline.length === 0) {
                    return data;
                }

                const color = opts.color || '#2563eb';
                const weight = opts.weight || 4;
                const dashArray = data.is_fallback ? '8, 8' : null;

                _routeLayer = L.polyline(data.polyline, {
                    color,
                    weight,
                    opacity: 0.85,
                    dashArray,
                }).addTo(_map);

                // Fit to show the whole route
                _map.fitBounds(_routeLayer.getBounds(), { padding: [50, 50] });

                if (opts.onRouteReady) opts.onRouteReady(data);
                return data;
            });
    }

    /** Clear the drawn route. */
    function clearRoute() {
        if (_routeLayer) {
            _map.removeLayer(_routeLayer);
            _routeLayer = null;
        }
    }

    // ──────────────────────────────────────────
    //  Map drag → update pin
    // ──────────────────────────────────────────

    /**
     * Make a marker draggable and update hidden inputs + reverse geocode on drag.
     */
    function makeDraggablePin(markerId, opts = {}) {
        const marker = _markers[markerId];
        if (!marker) return;

        marker.dragging.enable();

        marker.on('dragend', (e) => {
            const ll = e.target.getLatLng();
            const lat = ll.lat.toFixed(6);
            const lon = ll.lng.toFixed(6);

            if (opts.latInputId) document.getElementById(opts.latInputId).value = lat;
            if (opts.lonInputId) document.getElementById(opts.lonInputId).value = lon;

            // Reverse geocode
            fetch(`/api/reverse-geocode/?lat=${lat}&lon=${lon}`)
                .then(r => r.json())
                .then(data => {
                    if (data.formatted_address && opts.addressInputId) {
                        document.getElementById(opts.addressInputId).value = data.formatted_address;
                    }
                })
                .catch(() => {});
        });
    }

    // ──────────────────────────────────────────
    //  Public API
    // ──────────────────────────────────────────

    return {
        init,
        getMap,
        ICONS,
        addMarker,
        removeMarker,
        getMarker,
        panToMarker,
        fitAllMarkers,
        useCurrentLocation,
        setSearchBox,
        drawRoute,
        clearRoute,
        makeDraggablePin,
    };
})();
