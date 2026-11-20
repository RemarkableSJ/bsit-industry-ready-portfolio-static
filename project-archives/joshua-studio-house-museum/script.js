// Joshua's Studio House Museum — static presentation mode.
// All cart and request interactions are local browser demonstrations.
// --- Global State ---
        window.state = {
            currentSection: 'home',
            currentFilter: 'All',
            cart: [],
            checkoutStep: 'cart', 
            selectedPaymentMethod: null,
            selectedDeliveryMethod: 'shipping',
            shippingDetails: {},
            paymentReference: '',
            showroomIndices: { Graphite: 0, Canvas: 0, Artifacts: 0 },
            showrooms: [
                {
                    id: 'Graphite',
                    title: 'Graphite Hall',
                    images: ['assets/images/Anakin Skywalker Portrait.jpg', 'assets/images/Paul Atreides Portrait.jpg', 'assets/images/Willy Wonka Portrait.jpg']
                },
                {
                    id: 'Canvas',
                    title: 'Canvas Wing',
                    images: ['assets/images/Atomic Bomb Explosion - Canvas Painting.jpg', 'assets/images/Homer Hiding in Bush - Canvas Painting.jpg']
                },
                {
                    id: 'Artifacts',
                    title: 'Artisan Artifacts',
                    images: ['assets/images/Staedtler Mars Lumograph.jpg', 'assets/images/Faber-Castell 9000.jpg', 'assets/images/Drawing Erasers.jpg']
                }
            ],
            portfolioItems: [] 
        };

        // --- Initial Inventory Data (Images updated to placeholders for preview) ---
        const initialInventory = [
            { id: 1, title: 'Anakin Skywalker', category: 'Graphite', img: 'assets/images/Anakin Skywalker Portrait.jpg', medium: 'Pencil on Bond Paper', year: '2026', type: 'art', donation: 150 },
            { id: 2, title: 'Paul Atreides', category: 'Graphite', img: 'assets/images/Paul Atreides Portrait.jpg', medium: 'Pencil on Bond Paper', year: '2026', type: 'art', donation: 150 },
            { id: 3, title: 'Willy Wonka', category: 'Graphite', img: 'assets/images/Willy Wonka Portrait.jpg', medium: 'Pencil on Bond Paper', year: '2026', type: 'art', donation: 150 },
            { id: 4, title: 'Homelander', category: 'Graphite', img: 'assets/images/Homelander Portrait.jpg', medium: 'Pencil on Bond Paper', year: '2026', type: 'art', donation: 150 },
            { id: 14, title: 'Billy Butcher', category: 'Graphite', img: 'assets/images/Billy Butcher Portrait.jpg', medium: 'Pencil on Bond Paper', year: '2026', type: 'art', donation: 150 },
            { id: 15, title: 'Dr. Saul Durand', category: 'Graphite', img: 'assets/images/Dr. Saul Durand Portrait.jpg', medium: 'Pencil on Bond Paper', year: '2026', type: 'art', donation: 150 },
            { id: 16, title: 'RoboCop (Murphy)', category: 'Graphite', img: 'assets/images/Peter Weller Portrait.jpg', medium: 'Pencil on Bond Paper', year: '2026', type: 'art', donation: 150 },
            { id: 17, title: 'Murphy (Z Nation)', category: 'Graphite', img: 'assets/images/Murphy Portrait.jpg', medium: 'Pencil on Bond Paper', year: '2026', type: 'art', donation: 150 },
            { id: 13, title: 'Premium Bond Paper', category: 'Graphite', img: 'assets/images/Bond Paper.jpg', medium: 'High-Grade A4 Sheet', year: 'Material', type: 'material', donation: 20, variants: [], hasSize: false },
            { id: 40, title: 'Nuclear Dawn', category: 'Canvas', img: 'assets/images/Atomic Bomb Explosion - Canvas Painting.jpg', medium: 'Acrylic on Canvas', year: '2026', type: 'art', donation: 8500 },
            { id: 18, title: 'Homer in the Hedges', category: 'Canvas', img: 'assets/images/Homer Hiding in Bush - Canvas Painting.jpg', medium: 'Acrylic on Canvas', year: '2026', type: 'art', donation: 5000 },
            { id: 11, title: 'Blank Studio Canvas', category: 'Canvas', img: 'assets/images/Blank Canvas.jpg', medium: 'Primed Cotton (25x30cm)', year: 'Material', type: 'material', donation: 65, variants: [], hasSize: false },
            
            // PENCILS: With specific prices per variant
            { 
                id: 6, title: 'Staedtler Mars Lumograph', category: 'Artifacts', img: 'assets/images/Staedtler Mars Lumograph.jpg', medium: 'Drawing Pencils', year: 'Supply', type: 'supply', donation: 50, 
                variants: [
                    { name: '8B', stock: 2, price: 47 }, { name: '7B', stock: 2, price: 47 }, { name: '6B', stock: 2, price: 47 }, { name: '5B', stock: 2, price: 47 }, 
                    { name: '4B', stock: 2, price: 47 }, { name: '3B', stock: 2, price: 47 }, { name: '2B', stock: 2, price: 47 }, { name: 'B', stock: 2, price: 47 }, 
                    { name: 'HB', stock: 0, price: 47 }, { name: 'F', stock: 2, price: 47 }, { name: 'H', stock: 2, price: 47 }, { name: '2H', stock: 2, price: 47 }, 
                    { name: '3H', stock: 2, price: 47 }, { name: '4H', stock: 2, price: 47 }, { name: '5H', stock: 2, price: 47 }, { name: '6H', stock: 2, price: 47 }
                ] 
            },
            { 
                id: 7, title: 'Faber-Castell 9000', category: 'Artifacts', img: 'assets/images/Faber-Castell 9000.jpg', medium: 'Drawing Pencils', year: 'Supply', type: 'supply', donation: 35,
                variants: [
                    { name: '8B', stock: 2, price: 30 }, { name: '7B', stock: 2, price: 30 }, { name: '6B', stock: 2, price: 30 }, { name: '5B', stock: 2, price: 30 }, 
                    { name: '4B', stock: 2, price: 30 }, { name: '3B', stock: 2, price: 30 }, { name: '2B', stock: 2, price: 30 }, { name: 'B', stock: 2, price: 30 }, 
                    { name: 'HB', stock: 2, price: 30 }, { name: 'F', stock: 2, price: 30 }, { name: 'H', stock: 2, price: 30 }, { name: '2H', stock: 2, price: 30 }, 
                    { name: '3H', stock: 2, price: 30 }, { name: '4H', stock: 2, price: 30 }, { name: '5H', stock: 2, price: 30 }, { name: '6H', stock: 2, price: 30 }
                ]
            },
            // ERASERS: With specific prices per variant
            { 
                id: 8, title: 'Drawing Erasers', category: 'Artifacts', img: 'assets/images/Drawing Erasers.jpg', medium: 'Best Erasers', year: 'Supply', type: 'supply', donation: 45,
                variants: [ { name: 'Staedler Mars Plastic Eraser', stock: 5, price: 65 }, { name: 'Faber-Castell Kneadable Eraser', stock: 5, price: 60 } ]
            },
            { id: 9, title: 'Customized Ecobag (Mystery)', category: 'Curated', img: 'assets/images/Mystery Ecobag.jpg', medium: 'Pre-Printed Canvas', year: 'Edition 1', type: 'art', donation: 100 },
            
            // ECOBAG: With 2 sizes and different prices. IMPORTANT: hasSize must be false now that we use variants.
            { 
                id: 12, title: 'Plain Artisan Ecobag', category: 'Curated', img: 'assets/images/Ecobag.jpg', medium: 'Undyed Heavy Cotton', year: 'Material', type: 'material', donation: 250, 
                variants: [
                    { name: 'Regular (8.5x10.5)', stock: 20, price: 40 },
                    { name: 'Large (10x12)', stock: 20, price: 50}
                ],
                hasSize: false 
            }
        ];

        // --- LOCAL PRESENTATION DATA ---
function saveDemoInventory() {
    try {
        localStorage.setItem('museum_demo_inventory', JSON.stringify(window.state.portfolioItems));
    } catch (error) {
        console.warn('Demo inventory could not be saved in this browser.', error);
    }
}

async function deductInventoryFromItems(items) {
    for (const cartItem of (items || [])) {
        if ((cartItem.type === 'supply' || cartItem.type === 'material') && cartItem.selectedVariant) {
            const product = window.state.portfolioItems.find(item => item.id === cartItem.baseId);
            const variant = product?.variants?.find(v => v.name === cartItem.selectedVariant);
            if (variant) variant.stock = Math.max(0, Number(variant.stock || 0) - Number(cartItem.quantity || 0));
        }
    }
    saveDemoInventory();
}

async function initializeDatabase() {
    // Use a local, browser-only copy of the inventory for presentation.
    try {
        const saved = JSON.parse(localStorage.getItem('museum_demo_inventory') || 'null');
        window.state.portfolioItems = Array.isArray(saved) && saved.length ? saved : JSON.parse(JSON.stringify(initialInventory));
    } catch (error) {
        window.state.portfolioItems = JSON.parse(JSON.stringify(initialInventory));
    }
    render();
}

// --- WINDOW FUNCTIONS ---
        window.toggleMenu = () => {
            const menu = document.getElementById('mobile-menu');
            const icon = document.getElementById('menu-icon');
            if (menu) {
                menu.classList.toggle('hidden');
                menu.classList.toggle('flex');
            }
        }

        window.showSection = (sectionId) => {
            window.state.currentSection = sectionId;
            
            // Close mobile menu if open
            const menu = document.getElementById('mobile-menu');
            if (menu && !menu.classList.contains('hidden')) {
                menu.classList.add('hidden');
                menu.classList.remove('flex');
            }

            render();
            window.scrollTo(0,0);
        }

        window.setFilter = (cat) => {
            window.state.currentFilter = cat;
            render();
        }

        window.cycleShowroom = (id, direction) => {
            const showroom = window.state.showrooms.find(s => s.id === id);
            let current = window.state.showroomIndices[id];
            
            if (direction === 'next') {
                window.state.showroomIndices[id] = (current + 1) % showroom.images.length;
            } else {
                window.state.showroomIndices[id] = (current - 1 + showroom.images.length) % showroom.images.length;
            }
            render();
        }

        window.enterExhibit = (category) => {
            window.state.currentFilter = category;
            window.showSection('portfolio');
        }

        // Updates stock status AND displayed price dynamically
        window.updateStockDisplay = (itemId, variantName) => {
            const item = window.state.portfolioItems.find(i => i.id === itemId);
            if (!item || !item.variants) return;

            const variant = item.variants.find(v => v.name === variantName);
            const displayEl = document.getElementById(`stock-display-${itemId}`);
            const priceEl = document.getElementById(`price-display-text-${itemId}`);
            const btnEl = document.getElementById(`btn-acquire-${itemId}`);
            const qtyEl = document.getElementById(`qty-${itemId}`);

            if (variant) {
                // Update Price Display
                if (variant.price && priceEl) {
                    priceEl.innerText = `₱${variant.price.toLocaleString()}`;
                }

                // Update Stock Display
                if (variant.stock > 0) {
                    if(displayEl) displayEl.innerHTML = `<span class="text-green-600 font-bold">In Stock: ${variant.stock} units</span>`;
                    if(btnEl) {
                        btnEl.disabled = false;
                        btnEl.classList.remove('opacity-50', 'cursor-not-allowed');
                        btnEl.innerText = "Acquire Item";
                    }
                    if(qtyEl) {
                        qtyEl.max = variant.stock;
                        qtyEl.value = 1;
                        qtyEl.disabled = false;
                    }
                } else {
                    if(displayEl) displayEl.innerHTML = `<span class="text-red-500 font-bold tracking-widest">OUT OF STOCK</span>`;
                    if(btnEl) {
                        btnEl.disabled = true;
                        btnEl.classList.add('opacity-50', 'cursor-not-allowed');
                        btnEl.innerText = "Unavailable";
                    }
                    if(qtyEl) {
                        qtyEl.value = 0;
                        qtyEl.disabled = true;
                    }
                }
            }
        }

        window.addToCart = (id, variant = null, size = null, qty = 1) => {
            const item = window.state.portfolioItems.find(p => p.id === id);
            let finalDonation = item.donation;
            let finalTitle = item.title;

            // Check Stock and Price for Variants
            if (item.variants && item.variants.length > 0) {
                const variantObj = item.variants.find(v => v.name === variant);
                if (variantObj) {
                    if (variantObj.stock < qty) {
                        alert("Sorry, there is insufficient stock for this request.");
                        return;
                    }
                    // Use variant price if available
                    if (variantObj.price) {
                        finalDonation = variantObj.price;
                    }
                }
            }

            if (size) {
                if (size === '8.5x10.5') finalDonation = 40; 
                else if (size === '10x12') finalDonation = 60; 
                finalTitle = `${item.title} (${size})`;
            }

            if (variant) finalTitle = `${item.title} - ${variant}`;

            const cartId = `${id}-${variant || ''}-${size || ''}`; 
            const existing = window.state.cart.find(c => c.cartId === cartId);

            if (existing) {
                existing.quantity += parseInt(qty);
            } else {
                window.state.cart.push({
                    ...item,
                    cartId: cartId,
                    title: finalTitle,
                    donation: finalDonation,
                    quantity: parseInt(qty),
                    selectedVariant: variant,
                    selectedSize: size,
                    baseId: item.id
                });
            }
            window.updateCartBadge();
            window.showSection('cart');
        }

        window.removeFromCart = (cartId) => {
            window.state.cart = window.state.cart.filter(i => i.cartId !== cartId);
            render();
        }

        window.startCommission = (type) => {
            window.showSection('commissions');
            setTimeout(() => {
                const select = document.getElementById('commission-type');
                if (select) {
                    select.value = type;
                    window.updateMinDonation();
                }
            }, 100);
        }

        window.updateMinDonation = () => {
            const type = document.getElementById('commission-type').value;
            const hint = document.getElementById('donation-hint');
            const input = document.getElementById('donation-amount');
            
            let min = 0;
            if (type === 'Ecobag') min = 50;
            else if (type === 'Portrait' || type === 'Canvas') min = 100;
            
            if (min > 0) {
                hint.innerText = `Required Donation: ₱${min} Minimum`;
                input.min = min;
                input.placeholder = `Minimum ₱${min}`;
            } else {
                hint.innerText = 'Please select a commission type';
                input.placeholder = 'Enter amount...';
            }
        }

        // --- PAYMENT & LOGISTICS LOGIC ---

        // Toggle for Cart Page
        window.toggleDelivery = (method) => {
            window.state.selectedDeliveryMethod = method;
            const shippingForm = document.getElementById('shipping-form');
            const pickupInfo = document.getElementById('pickup-info');
            
            if (method === 'shipping') {
                shippingForm.classList.remove('hidden');
                pickupInfo.classList.add('hidden');
            } else {
                shippingForm.classList.add('hidden');
                pickupInfo.classList.remove('hidden');
            }
        }

        // Toggle for Commission Page
        window.toggleCommDelivery = (method) => {
            const shipForm = document.getElementById('comm-shipping-form');
            const pickupInfo = document.getElementById('comm-pickup-info');
            const addrInput = document.getElementById('comm-ship-addr');
            const phoneInput = document.getElementById('comm-ship-phone');

            if (method === 'shipping') {
                shipForm.classList.remove('hidden');
                pickupInfo.classList.add('hidden');
                if(addrInput) addrInput.required = true;
                if(phoneInput) phoneInput.required = true;
            } else {
                shipForm.classList.add('hidden');
                pickupInfo.classList.remove('hidden');
                if(addrInput) addrInput.required = false;
                if(phoneInput) phoneInput.required = false;
            }
        }


        window.setCheckoutStep = (step) => {
            window.state.checkoutStep = step;
            window.showSection('cart');
        }

        window.resetOrder = () => {
            window.state.checkoutStep = 'cart';
            window.showSection('home');
        }

        window.updateCartBadge = () => {
            const badge = document.getElementById('cart-count');
            if (badge) {
                const count = window.state.cart.reduce((sum, item) => sum + item.quantity, 0);
                badge.innerText = count;
                badge.classList.toggle('hidden', count === 0);
            }
        }

        // --- RENDERING ---

        function render() {
            const root = document.getElementById('app-root');
            const s = window.state;
            
            if (s.currentSection === 'home') root.innerHTML = renderHome();
            else if (s.currentSection === 'portfolio') root.innerHTML = renderPortfolio();
            else if (s.currentSection === 'commissions') root.innerHTML = renderCommissions(); // THIS NOW WORKS
            else if (s.currentSection === 'cart') root.innerHTML = renderCart();
            
            window.lucide?.createIcons?.();
            window.updateCartBadge();
            
            
        }

        // --- THE MISSING FUNCTION HAS BEEN ADDED HERE ---
        function renderCommissions() {
            return `
                <div class="max-w-3xl mx-auto px-8 py-20 animate-reveal">
                    <h2 class="museum-font text-4xl uppercase tracking-widest mb-4 text-center">Patronage Request</h2>
                    <p class="text-center text-stone-500 italic serif mb-12">Commission a bespoke piece from the studio.</p>

                    <form onsubmit="window.processCommissionCheckout(event)" class="space-y-4">
                        
                        <!-- Commission Type -->
                        <div>
                            <label class="museum-label">Commission Type</label>
                            <div class="relative">
                                <select id="commission-type" onchange="window.updateMinDonation()" class="museum-input appearance-none bg-transparent" required>
                                    <option value="" disabled selected>Select Request Type...</option>
                                    <option value="Portrait">Graphite Portrait (from ₱100)</option>
                                    <option value="Canvas">Canvas Painting (from ₱100)</option>
                                    <option value="Ecobag">Hand-Painted Ecobag (from ₱50)</option>
                                </select>
                                <i data-lucide="chevron-down" class="absolute right-0 top-3 w-4 h-4 text-stone-400 pointer-events-none"></i>
                            </div>
                            <p id="donation-hint" class="text-[9px] text-[#c2a382] mt-2 font-bold uppercase tracking-widest"></p>
                        </div>

                        <!-- Personal Details -->
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
                            <div>
                                <label class="museum-label">Patron Name</label>
                                <input type="text" class="museum-input" required placeholder="Your Full Name">
                            </div>
                            <div>
                                <label class="museum-label">Email Address</label>
                                <input type="email" class="museum-input" required placeholder="contact@email.com">
                            </div>
                        </div>

                        <!-- Vision/Details -->
                        <div>
                            <label class="museum-label">Artistic Vision / Details</label>
                            <textarea class="museum-input resize-none h-32" required placeholder="Describe your request (subject, mood, size preferences)..."></textarea>
                        </div>

                        <!-- Donation Offer -->
                        <div>
                            <label class="museum-label">Proposed Donation (PHP)</label>
                            <input type="number" id="donation-amount" class="museum-input font-serif text-lg" required min="50">
                        </div>

                        <hr class="border-stone-100 my-4">

                        <!-- Delivery Method -->
                        <div>
                            <label class="museum-label mb-4 block">Delivery Preference</label>
                            <div class="flex gap-8 mb-6">
                                <label class="flex items-center gap-2 cursor-pointer">
                                    <input type="radio" name="comm-delivery" value="shipping" checked onchange="window.toggleCommDelivery('shipping')" class="accent-[#c2a382]">
                                    <span class="text-xs uppercase tracking-widest">Shipping</span>
                                </label>
                                <label class="flex items-center gap-2 cursor-pointer">
                                    <input type="radio" name="comm-delivery" value="pickup" onchange="window.toggleCommDelivery('pickup')" class="accent-[#c2a382]">
                                    <span class="text-xs uppercase tracking-widest">Studio Pickup</span>
                                </label>
                            </div>

                            <!-- Shipping Fields -->
                            <div id="comm-shipping-form" class="space-y-4 animate-reveal">
                                <div><label class="museum-label">Delivery Address</label><input type="text" id="comm-ship-addr" class="museum-input" required></div>
                                <div><label class="museum-label">Contact Number</label><input type="text" id="comm-ship-phone" class="museum-input" required></div>
                            </div>

                            <!-- Pickup Info -->
                            <div id="comm-pickup-info" class="hidden bg-stone-50 p-4 border border-dashed border-stone-200 text-center animate-reveal">
    <p class="text-[10px] text-stone-500 mb-4">Pickup location details will be confirmed by the studio</p>
    <div class="space-y-4 text-left">
        <div>
            <label class="museum-label">Pickup Name</label>
            <input type="text" id="comm-pickup-name" class="museum-input">
        </div>
        <div>
            <label class="museum-label">Contact Number</label>
            <input type="text" id="comm-pickup-phone" class="museum-input">
        </div>
    </div>
</div>
                        </div>

                        <div class="bg-stone-50 border border-dashed border-stone-300 p-4 text-center">
    <p class="text-[10px] uppercase tracking-widest font-bold text-stone-600">Presentation mode</p>
    <p class="text-xs text-stone-500 mt-2">This form demonstrates the commission request flow only. It does not submit a real order or process payment.</p>
</div>

<button type="submit" class="w-full bg-black text-white py-5 text-[10px] uppercase tracking-[0.25em] font-bold hover:bg-[#c2a382] transition-colors mt-4">
    Submit demo request
</button>
                    </form>
                </div>
            `;
        }

        function renderHome() {
            const s = window.state;
            return `
                <section class="py-24 px-8 bg-black text-white text-center">
                    <div class="max-w-4xl mx-auto animate-reveal">
                        <p class="text-[10px] uppercase tracking-[0.8em] mb-6 opacity-60">Permanent Archives</p>
                        <h1 class="text-4xl md:text-7xl museum-font uppercase tracking-widest leading-tight">The Hall Showrooms</h1>
                        <div class="w-12 h-px bg-[#c2a382] mx-auto my-10"></div>
                        <p class="serif italic text-xl md:text-2xl opacity-70 max-w-2xl mx-auto">Explore curated works.</p>
                        <p class="text-[9px] uppercase tracking-[0.22em] text-white/50 mt-7">Presentation demo · checkout and commission flows are simulated locally</p>
                    </div>
                </section>

                <section class="px-8 pb-32 bg-black">
                    <div class="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-3 gap-8">
                        ${s.showrooms.map(room => {
                            const activeIdx = s.showroomIndices[room.id];
                            return `
                                <div class="showroom-card group animate-reveal">
                                    ${room.images.map((img, i) => `
                                        <img src="${img}" class="showroom-image ${i === activeIdx ? 'active' : ''}">
                                    `).join('')}
                                    <div class="absolute inset-0 bg-gradient-to-t from-black/90 via-transparent to-transparent flex flex-col justify-between p-10 z-20">
                                        <div class="flex justify-between items-start">
                                            <span class="text-[9px] uppercase tracking-[0.4em] text-white/40">Wing 0${s.showrooms.indexOf(room) + 1}</span>
                                            <div class="flex gap-2">
                                                <button onclick="event.stopPropagation(); window.cycleShowroom('${room.id}', 'prev')" class="mini-paddle w-8 h-8 rounded-full flex items-center justify-center text-white"><i data-lucide="chevron-left" class="w-4 h-4"></i></button>
                                                <button onclick="event.stopPropagation(); window.cycleShowroom('${room.id}', 'next')" class="mini-paddle w-8 h-8 rounded-full flex items-center justify-center text-white"><i data-lucide="chevron-right" class="w-4 h-4"></i></button>
                                            </div>
                                        </div>
                                        <div class="text-center">
                                            <h3 class="museum-font text-white text-3xl tracking-widest uppercase mb-6">${room.title}</h3>
                                            <button onclick="window.enterExhibit('${room.id}')" class="bg-white text-black px-8 py-3 text-[9px] uppercase tracking-[0.2em] font-bold hover:bg-[#c2a382] hover:text-white transition-all duration-300">Enter Collection</button>
                                        </div>
                                    </div>
                                </div>
                            `;
                        }).join('')}
                    </div>
                </section>
            `;
        }

        function renderPortfolio() {
            const s = window.state;
            if (!s.portfolioItems || s.portfolioItems.length === 0) {
                return `<div class="h-screen flex items-center justify-center"><p class="serif italic text-stone-400 animate-pulse">Retrieving Archives...</p></div>`;
            }

            const filtered = s.currentFilter === 'All' ? s.portfolioItems : s.portfolioItems.filter(i => i.category === s.currentFilter);
            const categories = ['All', 'Graphite', 'Canvas', 'Artifacts', 'Curated'];

            return `
                <div class="max-w-7xl mx-auto px-8 py-20 animate-reveal">
                    <header class="text-center mb-24">
                        <h2 class="museum-font text-5xl uppercase tracking-[0.2em] mb-12">The Wings</h2>
                        <div class="flex flex-wrap justify-center gap-12 border-b border-stone-200 pb-8">
                            ${categories.map(cat => `
                                <button onclick="window.setFilter('${cat}')" class="text-[10px] uppercase tracking-[0.3em] pb-2 border-b-2 transition-all ${s.currentFilter === cat ? 'border-black text-black font-bold' : 'border-transparent text-stone-400 hover:text-black'}">${cat} Hall</button>
                            `).join('')}
                        </div>
                    </header>

                    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-16">
                        ${filtered.map(item => {
                            // CALCULATE INITIAL DISPLAY PRICE
                            // If the item has variants (like pencils/ecobags), show the price of the first variant.
                            // Otherwise, show the base donation price.
                            let displayPrice = item.donation;
                            if (item.variants && item.variants.length > 0 && item.variants[0].price) {
                                displayPrice = item.variants[0].price;
                            }

                            return `
                                <div class="group">
                                    <div class="gallery-frame aspect-[4/5] bg-white mb-8 overflow-hidden relative shadow-lg">
                                        <img src="${item.img}" class="w-full h-full object-cover grayscale group-hover:grayscale-0 transition-all duration-1000 group-hover:scale-105">
                                        
                                        <div class="absolute inset-0 bg-black/80 opacity-0 group-hover:opacity-100 flex flex-col items-center justify-center transition-all duration-500 gap-4 p-6">
                                            
                                            ${item.variants && item.variants.length > 0 ? `
                                                <div class="w-full">
                                                    <label class="text-[9px] text-white uppercase tracking-widest block mb-2">
                                                        ${item.category === 'Curated' ? 'Select Size' : 'Select Series'}
                                                    </label>
                                                    <select id="variant-${item.id}" onchange="window.updateStockDisplay(${item.id}, this.value)" class="w-full bg-transparent border border-white text-white text-[10px] p-2 mb-2 outline-none">
                                                        ${item.variants.map(v => `<option value="${v.name}" class="text-black">${v.name}</option>`).join('')}
                                                    </select>
                                                    <p id="stock-display-${item.id}" class="text-[9px] text-[#c2a382] font-bold uppercase tracking-widest mb-4">In Stock: ${item.variants[0].stock}</p>
                                                </div>
                                            ` : ''}

                                            ${item.hasSize ? `
                                                <div class="w-full">
                                                    <label class="text-[9px] text-white uppercase tracking-widest block mb-2">Select Size</label>
                                                    <select id="size-${item.id}" class="w-full bg-transparent border border-white text-white text-[10px] p-2 mb-4 outline-none">
                                                        <option value="8.5x10.5" class="text-black">Small (8.5" x 10.5")</option>
                                                        <option value="10x12" class="text-black">Large (10" x 12")</option>
                                                    </select>
                                                </div>
                                            ` : ''}

                                            ${item.type !== 'art' ? `
                                                <div class="w-full flex items-center gap-4 mb-4">
                                                    <label class="text-[9px] text-white uppercase tracking-widest">Qty</label>
                                                    <input id="qty-${item.id}" type="number" min="1" max="99" value="1" class="w-16 bg-transparent border border-white text-white text-center text-[10px] p-2 outline-none">
                                                </div>
                                            ` : ''}

                                            <button id="btn-acquire-${item.id}" onclick="
                                                const variant = document.getElementById('variant-${item.id}')?.value || (window.state.portfolioItems.find(i=>i.id==${item.id}).variants && window.state.portfolioItems.find(i=>i.id==${item.id}).variants.length > 0 ? window.state.portfolioItems.find(i=>i.id==${item.id}).variants[0].name : null);
                                                const size = document.getElementById('size-${item.id}')?.value;
                                                const qty = document.getElementById('qty-${item.id}')?.value || 1;
                                                window.addToCart(${item.id}, variant, size, qty);
                                            " class="w-full text-white text-[9px] border border-white px-6 py-3 uppercase tracking-widest hover:bg-white hover:text-black transition-colors">
                                                Acquire ${item.type === 'material' || item.type === 'supply' ? 'Item' : 'Piece'}
                                            </button>

                                            ${item.type === 'material' ? `
                                                <button onclick="window.startCommission('${item.category === 'Canvas' ? 'Canvas' : 'Ecobag'}')" class="w-full text-[#c2a382] text-[9px] border border-[#c2a382] px-6 py-3 uppercase tracking-widest hover:bg-[#c2a382] hover:text-white transition-colors">Commission Art</button>
                                            ` : ''}
                                        </div>
                                    </div>
                                    <div class="text-center p-6 border border-stone-100 bg-white">
                                        <h3 class="museum-font text-lg font-bold mb-1 uppercase tracking-widest">${item.title}</h3>
                                        <p class="text-[9px] text-stone-400 uppercase tracking-[0.2em] mb-3">${item.year} — ${item.medium}</p>
                                        <p class="serif italic text-sm text-stone-600">
                                            <span id="price-display-text-${item.id}">₱${displayPrice.toLocaleString()}</span>
                                        </p>
                                    </div>
                                </div>
                            `;
                        }).join('')}
                    </div>
                </div>
            `;
        }

        function renderCart() {
            const s = window.state;
            const subtotal = s.cart.reduce((sum, item) => sum + (item.donation * item.quantity), 0);

            // 1. CONFIRMATION PAGE
            if (s.checkoutStep === 'confirmation') return `
                <div class="max-w-2xl mx-auto text-center py-20 animate-reveal">
                    <div class="w-24 h-24 border border-[#c2a382] rounded-full flex items-center justify-center mx-auto mb-10"><span class="text-4xl text-[#c2a382] serif italic">M</span></div>
                    <h2 class="museum-font text-4xl uppercase tracking-widest mb-6">Demo Completed</h2>
                    <p class="text-stone-500 mb-10 font-light max-w-md mx-auto leading-relaxed">Your demonstration checkout was completed in this browser only. No payment was processed, no real order was placed, and no fulfilment will occur.</p>
                    <button onclick="window.resetOrder()" class="text-xs uppercase tracking-widest font-bold border-b border-black pb-1 hover:text-[#c2a382] transition-all">Return to Grand Hall</button>
                </div>
            `;

            // 3. CART LIST / METHOD SELECTION
            return `
                <div class="max-w-3xl mx-auto px-8 py-20 animate-reveal">
                    <h2 class="museum-font text-3xl uppercase tracking-widest mb-16 text-center">Acquisitions Queue</h2>
                    ${s.cart.length === 0 ? `
                        <div class="text-center py-20 border border-dashed border-stone-200">
                            <p class="serif italic text-stone-400 mb-8">Your collection is currently empty.</p>
                            <button onclick="window.showSection('portfolio')" class="text-xs uppercase tracking-widest font-bold border-b border-black pb-1">Return to Halls</button>
                        </div>
                    ` : s.checkoutStep === 'cart' ? `
                        <!-- Step 1: List -->
                        <div class="space-y-12 mb-16">
                            ${s.cart.map(item => `
                                <div class="flex items-center gap-8 border-b border-stone-100 pb-8">
                                    <img src="${item.img}" class="w-20 h-24 object-cover grayscale">
                                    <div class="flex-1">
                                        <h4 class="museum-font text-lg uppercase tracking-widest">${item.title}</h4>
                                        <p class="text-[9px] text-stone-400 uppercase tracking-widest font-bold mt-1">${item.category} / ${item.year}</p>
                                        <p class="text-[10px] text-stone-500 mt-1 italic">${item.selectedVariant ? `Series: ${item.selectedVariant} | ` : ''}${item.selectedSize ? `Size: ${item.selectedSize} | ` : ''}Qty: ${item.quantity}</p>
                                    </div>
                                    <div class="text-right">
                                        <p class="serif text-sm italic mb-2">₱${(item.donation * item.quantity).toLocaleString()}</p>
                                        <button onclick="window.removeFromCart('${item.cartId}')" class="text-stone-300 hover:text-black transition-colors"><i data-lucide="x" class="w-5 h-5"></i></button>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                        <div class="bg-white p-12 border border-stone-100 text-center">
                            <div class="flex justify-between items-center mb-8 border-b border-stone-100 pb-4">
                                <span class="text-xs uppercase tracking-widest text-stone-500">Total Valuation</span>
                                <span class="serif text-2xl">₱${subtotal.toLocaleString()}</span>
                            </div>
                            <button onclick="window.setCheckoutStep('patronage')" class="w-full bg-black text-white py-5 text-[10px] uppercase tracking-[0.3em] font-bold hover:bg-[#c2a382] transition-colors">Submit Formal Acquisition Request</button>
                        </div>
                    ` : `
                        <!-- Step 2: Patronage Method & Logistics Selection -->
                        <div class="max-w-xl mx-auto bg-white p-12 border border-stone-100 shadow-xl">
                            
                            <!-- LOGISTICS -->
                            <h4 class="museum-font text-xl uppercase tracking-widest mb-6 mt-2 text-center">Logistics</h4>
                            <div class="grid grid-cols-2 gap-4 mb-8">
                                <label class="cursor-pointer">
                                    <input type="radio" name="delivery" value="shipping" class="peer hidden" checked onchange="window.toggleDelivery('shipping')">
                                    <div class="payment-badge text-center peer-checked:bg-[#fffaf5] peer-checked:border-[#c2a382] h-full flex flex-col items-center justify-center gap-2">
                                        <i data-lucide="truck" class="w-5 h-5 text-stone-400"></i>
                                        <span class="text-[10px] uppercase font-bold tracking-widest">Courier Delivery</span>
                                    </div>
                                </label>
                                <label class="cursor-pointer">
                                    <input type="radio" name="delivery" value="pickup" class="peer hidden" onchange="window.toggleDelivery('pickup')">
                                    <div class="payment-badge text-center peer-checked:bg-[#fffaf5] peer-checked:border-[#c2a382] h-full flex flex-col items-center justify-center gap-2">
                                        <i data-lucide="map-pin" class="w-5 h-5 text-stone-400"></i>
                                        <span class="text-[10px] uppercase font-bold tracking-widest">Studio Pickup</span>
                                    </div>
                                </label>
                            </div>

                            <!-- Shipping Inputs -->
                            <div id="shipping-form" class="space-y-4 mb-12 animate-reveal">
                                <div><label class="museum-label">Full Name</label><input type="text" id="ship-name" class="museum-input" required></div>
                                <div><label class="museum-label">Complete Address</label><input type="text" id="ship-addr" class="museum-input" required></div>
                                <div class="grid grid-cols-2 gap-4">
                                    <div><label class="museum-label">City</label><input type="text" id="ship-city" class="museum-input" required></div>
                                    <div><label class="museum-label">Contact No.</label><input type="text" id="ship-phone" class="museum-input" required></div>
                                </div>
                            </div>

                            <!-- Pickup Info -->
                            <div id="pickup-info" class="hidden mb-12 bg-stone-50 p-6 text-center border border-dashed border-stone-200 animate-reveal">
                                <p class="museum-font text-lg uppercase tracking-widest mb-2">Joshua's Studio</p>
                                <p class="text-xs text-stone-500 mb-4 leading-relaxed">Studio pickup details are provided directly when a real service is available<br>Open Daily: 10AM - 6PM</p>
                                <div class="text-left space-y-4">
                                    <div><label class="museum-label">Pickup Representative Name</label><input type="text" id="pickup-name" class="museum-input bg-white p-2"></div>
                                    <div><label class="museum-label">Contact No.</label><input type="text" id="pickup-phone" class="museum-input bg-white p-2"></div>
                                </div>
                            </div>

                            <hr class="border-stone-100 my-8">
                            <div class="bg-stone-50 border border-dashed border-stone-300 p-5 text-center">
                                <p class="text-[10px] uppercase tracking-widest font-bold text-stone-700">Demo checkout only</p>
                                <p class="text-xs text-stone-500 mt-2">The cart, delivery choices, totals, and confirmation screen are interactive demonstrations. No payment is taken and no real order is sent.</p>
                            </div>
                            <form onsubmit="window.processDemoCheckout(event)" class="mt-6">
                                <p class="text-xs text-stone-400 mb-4 uppercase tracking-widest text-center">
                                    Demonstration total: <span class="text-black font-bold">₱${subtotal.toLocaleString()}</span>
                                </p>
                                <div class="flex gap-4">
                                    <button type="button" onclick="window.setCheckoutStep('cart')" class="w-1/3 py-5 text-[10px] uppercase tracking-widest text-stone-400 hover:text-black border border-transparent hover:border-stone-200">Back</button>
                                    <button type="submit" class="w-2/3 bg-[#121212] text-white py-5 text-[10px] uppercase tracking-[0.25em] hover:bg-[#c2a382] transition-colors">Complete demo</button>
                                </div>
                            </form>
                        </div>
                    `}
                </div>
            `;
        }

// ==========================================
// LOCAL PRESENTATION CHECKOUT (NO PAYMENTS)
// ==========================================
window.processDemoCheckout = async function (event) {
    event.preventDefault();
    if (!window.state.cart.length) {
        alert('Your demonstration cart is empty.');
        return;
    }
    const method = document.querySelector('input[name="delivery"]:checked')?.value || 'shipping';
    let deliveryDetails = {};
    if (method === 'shipping') {
        const name = document.getElementById('ship-name')?.value?.trim() || '';
        const addr = document.getElementById('ship-addr')?.value?.trim() || '';
        const city = document.getElementById('ship-city')?.value?.trim() || '';
        const phone = document.getElementById('ship-phone')?.value?.trim() || '';
        if (!name || !addr || !city || !phone) {
            alert('Complete the demonstration delivery fields first.');
            return;
        }
        deliveryDetails = { type: 'shipping', name, addr, city, phone };
    } else {
        const name = document.getElementById('pickup-name')?.value?.trim() || '';
        const phone = document.getElementById('pickup-phone')?.value?.trim() || '';
        if (!name || !phone) {
            alert('Complete the demonstration pickup fields first.');
            return;
        }
        deliveryDetails = { type: 'pickup', name, phone };
    }
    const order = {
        id: 'DEMO-' + Date.now(),
        items: window.state.cart,
        total: window.state.cart.reduce((sum, item) => sum + (Number(item.donation) * Number(item.quantity)), 0),
        deliveryDetails,
        createdAt: new Date().toISOString(),
        mode: 'DEMO_ONLY_NO_PAYMENT_NO_REAL_ORDER'
    };
    try {
        const history = JSON.parse(localStorage.getItem('museum_demo_orders') || '[]');
        history.push(order);
        localStorage.setItem('museum_demo_orders', JSON.stringify(history.slice(-20)));
        await deductInventoryFromItems(window.state.cart);
    } catch (error) {
        console.warn('The demo checkout could not be saved in this browser.', error);
    }
    window.state.cart = [];
    localStorage.removeItem('cart');
    window.state.checkoutStep = 'confirmation';
    render();
};

window.processCommissionCheckout = function (event) {
    event.preventDefault();
    const form = event.target;
    if (!form.reportValidity()) return;
    const type = document.getElementById('commission-type')?.value || '';
    const amount = Number(document.getElementById('donation-amount')?.value || 0);
    const minimum = type === 'Ecobag' ? 50 : (type === 'Portrait' || type === 'Canvas' ? 100 : 0);
    if (!type || amount < minimum) {
        alert(`Please check the request type and minimum demonstration amount (₱${minimum}).`);
        return;
    }
    const textInputs = form.querySelectorAll('input[type="text"]');
    const email = form.querySelector('input[type="email"]')?.value?.trim() || '';
    const request = {
        id: 'DEMO-COMM-' + Date.now(),
        type,
        amount,
        patron: textInputs[0]?.value?.trim() || '',
        email,
        vision: form.querySelector('textarea')?.value?.trim() || '',
        delivery: document.querySelector('input[name="comm-delivery"]:checked')?.value || 'shipping',
        createdAt: new Date().toISOString(),
        mode: 'DEMO_ONLY_NO_PAYMENT_NO_REAL_REQUEST'
    };
    try {
        const history = JSON.parse(localStorage.getItem('museum_demo_commissions') || '[]');
        history.push(request);
        localStorage.setItem('museum_demo_commissions', JSON.stringify(history.slice(-20)));
    } catch (error) {
        console.warn('The demo request could not be saved in this browser.', error);
    }
    alert('Demo commission request recorded in this browser only. No real request or payment was submitted.');
    window.showSection('home');
};

initializeDatabase();