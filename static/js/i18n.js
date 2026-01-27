/**
 * HA Entity Explorer - Internationalization (i18n)
 * Supports French (fr) and English (en) languages.
 */

const translations = {
    fr: {
        // App title
        appTitle: "HA Entity Explorer",

        // Entity search
        searchPlaceholder: "Rechercher une entité...",
        loadingEntities: "Chargement des entités...",
        noEntitiesFound: "Aucune entité trouvée",
        failedToLoadEntities: "Échec du chargement des entités",

        // Date range
        period: "Période",
        selectDateRange: "Sélectionner une période",
        from: "Du",
        to: "Au",
        quickSelect: "Sélection rapide",
        day: "jour",
        days: "jours",
        apply: "Appliquer",
        cancel: "Annuler",
        refresh: "Actualiser",

        // Chart
        selectEntityPrompt: "Sélectionnez une entité pour voir son historique",
        noHistoryData: "Pas de données d'historique pour cette période",
        failedToLoadHistory: "Échec du chargement de l'historique",

        // Climate chart labels
        interior: "Intérieur",
        setpoint: "Consigne",
        exterior: "Extérieur",
        heating: "Chauffe",
        value: "Valeur",

        // Details panel
        detailsAt: "Détails à",
        clickToSeeDetails: "Cliquez sur le graphique pour voir les détails.",
        noAttributesAvailable: "Aucun attribut disponible",
        back: "Retour",
        items: "éléments",

        // History modal
        history: "Historique",
        time: "Heure",
        loading: "Chargement...",
        failedToLoadAttributeHistory: "Échec du chargement de l'historique de l'attribut",

        // Errors
        errorDateRange: "Veuillez sélectionner les dates de début et de fin",
        errorDateOrder: "La date de début doit être antérieure à la date de fin",
        entityNotAllowed: "Accès à cette entité non autorisé"
    },

    en: {
        // App title
        appTitle: "HA Entity Explorer",

        // Entity search
        searchPlaceholder: "Search for an entity...",
        loadingEntities: "Loading entities...",
        noEntitiesFound: "No entities found",
        failedToLoadEntities: "Failed to load entities",

        // Date range
        period: "Period",
        selectDateRange: "Select Date Range",
        from: "From",
        to: "To",
        quickSelect: "Quick Select",
        day: "day",
        days: "days",
        apply: "Apply",
        cancel: "Cancel",
        refresh: "Refresh",

        // Chart
        selectEntityPrompt: "Select an entity to view its history",
        noHistoryData: "No history data available for this period",
        failedToLoadHistory: "Failed to load history",

        // Climate chart labels
        interior: "Interior",
        setpoint: "Setpoint",
        exterior: "Exterior",
        heating: "Heating",
        value: "Value",

        // Details panel
        detailsAt: "Details at",
        clickToSeeDetails: "Click on the chart to see details.",
        noAttributesAvailable: "No attributes available",
        back: "Back",
        items: "items",

        // History modal
        history: "History",
        time: "Time",
        loading: "Loading...",
        failedToLoadAttributeHistory: "Failed to load attribute history",

        // Errors
        errorDateRange: "Please select both start and end dates",
        errorDateOrder: "Start date must be before end date",
        entityNotAllowed: "Access to this entity is not allowed"
    }
};

// Current language (will be set from config)
let currentLang = 'en';

/**
 * Set the current language.
 * @param {string} lang - Language code ('fr' or 'en')
 */
function setLanguage(lang) {
    if (translations[lang]) {
        currentLang = lang;
        updateUILanguage();
    } else {
        console.warn(`Language '${lang}' not supported, falling back to 'en'`);
        currentLang = 'en';
    }
}

/**
 * Get a translation by key.
 * @param {string} key - Translation key
 * @returns {string} Translated string or the key if not found
 */
function t(key) {
    return translations[currentLang]?.[key] || translations['en']?.[key] || key;
}

/**
 * Update all UI elements with data-i18n attributes.
 */
function updateUILanguage() {
    // Update text content
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        el.textContent = t(key);
    });

    // Update placeholders
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        const key = el.getAttribute('data-i18n-placeholder');
        el.placeholder = t(key);
    });

    // Update titles/tooltips
    document.querySelectorAll('[data-i18n-title]').forEach(el => {
        const key = el.getAttribute('data-i18n-title');
        el.title = t(key);
    });

    // Update aria-labels
    document.querySelectorAll('[data-i18n-aria]').forEach(el => {
        const key = el.getAttribute('data-i18n-aria');
        el.setAttribute('aria-label', t(key));
    });
}

/**
 * Format a date according to current language.
 * @param {Date} date - Date to format
 * @param {boolean} includeTime - Whether to include time
 * @returns {string} Formatted date string
 */
function formatDate(date, includeTime = true) {
    const locale = currentLang === 'fr' ? 'fr-FR' : 'en-US';
    const options = {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric'
    };

    if (includeTime) {
        options.hour = '2-digit';
        options.minute = '2-digit';
    }

    return date.toLocaleString(locale, options);
}

/**
 * Format a time according to current language.
 * @param {Date} date - Date to format
 * @returns {string} Formatted time string
 */
function formatTime(date) {
    const locale = currentLang === 'fr' ? 'fr-FR' : 'en-US';
    return date.toLocaleTimeString(locale, {
        hour: '2-digit',
        minute: '2-digit'
    });
}

/**
 * Get the date range display text.
 * @param {Date} start - Start date
 * @param {Date} end - End date
 * @returns {string} Formatted range string
 */
function formatDateRange(start, end) {
    const fromLabel = t('from').toLowerCase();
    const toLabel = t('to').toLowerCase();
    return `${fromLabel} ${formatDate(start)} ${toLabel} ${formatDate(end)}`;
}

// Export for use in other modules
window.i18n = {
    setLanguage,
    t,
    updateUILanguage,
    formatDate,
    formatTime,
    formatDateRange,
    getCurrentLang: () => currentLang
};
