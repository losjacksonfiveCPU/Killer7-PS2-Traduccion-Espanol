from pathlib import Path

path = Path("source/src/environment/app_picker.rs")
src = path.read_text()

def replace_once(old, new):
    global src
    count = src.count(old)
    if count != 1 and not (count == 2 and old.startswith('        () = msg![env; button setFrame:button_frame];')):
        raise RuntimeError(f"Expected exactly one match, found {count}: {old[:110]!r}")
    src = src.replace(old, new, 1)

# No binary manipulation: remove the visual watermark at source level.
start = src.index('    let brand_color: id = if crate::branding() == "UNOFFICIAL" {')
end = src.index('    let divider = app_frame.size.height - 100.0;', start)
src = src[:start] + '    // Spanish glass edition: keep upstream branding data but never paint red watermark.\n\n' + src[end:]

start = src.index('        let text = ns_string::from_rust_string(\n            env,\n            format!(\n                "iDared 32bit {}{}{}",')
end = src.index('        () = msg![env; label setText:text];', start)
src = src[:start] + '''        let text = ns_string::from_rust_string(
            env,
            format!("iDared 32bit · v{}", crate::DISPLAY_VERSION),
        );
''' + src[end:]

# Black backdrop, never read an optional old wallpaper from the data directory.
replace_once(
    '    // Wallpaper\n',
    '''    // Black backdrop without binary modifications or an external wallpaper.
    let black: id = msg_class![env; UIColor blackColor];
    () = msg![env; main_view setBackgroundColor:black];

    // Wallpaper (disabled in this edition to keep the background solid black).
'''
)
replace_once('    for candidate in paths::WALLPAPER_FILES {',
             '    for candidate in std::iter::empty::<&str>() {')

# Spanish UI labels (game titles and legal licence text remain untouched).
translations = {
    '"The {} directory couldn\'t be found. Check you\'re running touchHLE from the right directory."':
    '"No se encontró la carpeta {}. Comprueba la instalación de iDared."',
    '"Couldn\'t get list of apps in the {} directory: {}."':
    '"No se pudieron leer los juegos de la carpeta {}: {}."',
    '"No apps were found in the {} directory."':
    '"No se encontraron juegos en la carpeta {}."',
    '("File manager", "openFileManager")': '("Archivos", "openFileManager")',
    '("Quick options", "quickOptionsShow")': '("Ajustes", "quickOptionsShow")',
    '("Copyright info", "copyrightInfoShow")': '("Licencias", "copyrightInfoShow")',
    '("iDared 32bit Code", "visitWebsite")': '("Código fuente", "visitWebsite")',
    'RowKind::Label("Scale hack")': 'RowKind::Label("Escalado")',
    '("Default", "scaleHackDefault")': '("Normal", "scaleHackDefault")',
    '("Off", "scaleHack1")': '("Sin", "scaleHack1")',
    'RowKind::Label("Orientation")': 'RowKind::Label("Orientación")',
    '("Default", "orientationDefault")': '("Normal", "orientationDefault")',
    'RowKind::Label("Network access")': 'RowKind::Label("Acceso a internet")',
    'RowKind::Label("Use analog sticks for tilt controls")': 'RowKind::Label("Mandos: control por inclinación")',
    'RowKind::Label("Fullscreen (override)")': 'RowKind::Label("Forzar pantalla completa")',
}
for old, new in translations.items():
    replace_once(old, new)

# Subtle native pseudo-glass buttons (no dependency on a PNG in the IPA).
replace_once(
    '        () = msg![env; button setFrame:button_frame];\n        // FIXME: manually calling layoutSubviews',
    '''        () = msg![env; button setFrame:button_frame];
        let translucent: id = msg_class![env; UIColor colorWithWhite:(0.22 as CGFloat) alpha:(0.72 as CGFloat)];
        () = msg![env; button setBackgroundColor:translucent];
        let white: id = msg_class![env; UIColor whiteColor];
        () = msg![env; button setTitleColor:white forState:UIControlStateNormal];
        let layer: id = msg![env; button layer];
        () = msg![env; layer setCornerRadius:(14.0 as CGFloat)];
        // FIXME: manually calling layoutSubviews'''
)

# Save quick settings in the app's own user data directory.
settings_code = '''
#[derive(Clone, Copy)]
struct SavedQuickSettings {
    scale_hack: Option<NonZeroU32>,
    orientation: Option<DeviceOrientation>,
    analog_stick_tilt_controls: bool,
    network: bool,
    fullscreen: bool,
}
impl Default for SavedQuickSettings {
    fn default() -> Self {
        Self {
            scale_hack: None,
            orientation: None,
            analog_stick_tilt_controls: true,
            network: false,
            fullscreen: false,
        }
    }
}

fn quick_settings_path() -> PathBuf {
    paths::user_data_base_path().join("touchHLE_ajustes_es.txt")
}

fn load_quick_settings() -> SavedQuickSettings {
    let mut settings = SavedQuickSettings::default();
    let Ok(contents) = std::fs::read_to_string(quick_settings_path()) else {
        return settings;
    };
    for line in contents.lines() {
        let Some((key, value)) = line.split_once('=') else { continue; };
        match key {
            "scale" => {
                if value == "default" {
                    settings.scale_hack = None;
                } else if let Ok(factor) = value.parse::<u32>() {
                    if (1..=4).contains(&factor) {
                        settings.scale_hack = NonZeroU32::new(factor);
                    }
                }
            }
            "orientation" => settings.orientation = match value {
                "left" => Some(DeviceOrientation::LandscapeLeft),
                "right" => Some(DeviceOrientation::LandscapeRight),
                "inverted" => Some(DeviceOrientation::PortraitUpsideDown),
                _ => None,
            },
            "tilt" => settings.analog_stick_tilt_controls = value == "true",
            "network" => settings.network = value == "true",
            "fullscreen" => settings.fullscreen = value == "true",
            _ => (),
        }
    }
    settings
}

fn save_quick_settings(settings: SavedQuickSettings) {
    let orientation = match settings.orientation {
        None => "default",
        Some(DeviceOrientation::LandscapeLeft) => "left",
        Some(DeviceOrientation::LandscapeRight) => "right",
        Some(DeviceOrientation::PortraitUpsideDown) => "inverted",
        Some(DeviceOrientation::Portrait) => "default",
    };
    let scale = settings.scale_hack.map(|v| v.get().to_string())
        .unwrap_or_else(|| "default".to_string());
    let contents = format!(
        "scale={}\\\norientation={}\\\ntilt={}\\\nnetwork={}\\\nfullscreen={}\\\n",
        scale, orientation, settings.analog_stick_tilt_controls,
        settings.network, settings.fullscreen,
    );
    if let Err(err) = std::fs::write(quick_settings_path(), contents) {
        log!("No se pudieron guardar los ajustes: {}", err);
    }
}
'''
# The raw workflow step removes one escaping layer; normalize \n in Rust format only.
replace_once(
    'fn show_app_picker_gui(\n',
    settings_code + '\nfn show_app_picker_gui(\n'
)

replace_once(
    '''    let quick_options_stuff = setup_quick_options(env, delegate, main_view, app_frame);
    let mut quick_options_scale_hack: Option<NonZeroU32> = None;
    let mut quick_options_fullscreen: Option<()> = None;
    let mut quick_options_orientation: Option<DeviceOrientation> = None;
    let mut quick_options_analog_stick_tilt_controls = true;
    let mut quick_options_network = false;''',
    '''    let saved = load_quick_settings();
    let quick_options_stuff = setup_quick_options(env, delegate, main_view, app_frame, &saved);
    let mut quick_options_scale_hack = saved.scale_hack;
    let mut quick_options_fullscreen = if saved.fullscreen { Some(()) } else { None };
    let mut quick_options_orientation = saved.orientation;
    let mut quick_options_analog_stick_tilt_controls = saved.analog_stick_tilt_controls;
    let mut quick_options_network = saved.network;'''
)
replace_once(
    '''            let color: id = if idx == selected_idx {
                msg_class![env; UIColor magentaColor]
            } else {
                msg_class![env; UIColor grayColor]
            };''',
    '''            let color: id = if idx == selected_idx {
                msg_class![env; UIColor colorWithRed:(0.18 as CGFloat) green:(0.46 as CGFloat) blue:(0.94 as CGFloat) alpha:(0.92 as CGFloat)]
            } else {
                msg_class![env; UIColor colorWithWhite:(0.22 as CGFloat) alpha:(0.70 as CGFloat)]
            };'''
)

replace_once(
    '        let host_obj = env.objc.borrow_mut::<AppPickerDelegateHostObject>(delegate);\n\n        if std::mem::take(&mut host_obj.prev_page) {',
    '''        let host_obj = env.objc.borrow_mut::<AppPickerDelegateHostObject>(delegate);
        let quick_settings_changed =
            host_obj.scale_hack_default || host_obj.scale_hack1 ||
            host_obj.scale_hack2 || host_obj.scale_hack3 ||
            host_obj.scale_hack4 || host_obj.orientation_default ||
            host_obj.orientation_portrait_upside_down ||
            host_obj.orientation_landscape_left ||
            host_obj.orientation_landscape_right ||
            host_obj.analog_stick_tilt_controls.is_some() ||
            host_obj.network.is_some() || host_obj.fullscreen.is_some();

        if std::mem::take(&mut host_obj.prev_page) {'''
)
replace_once(
    '''        } else if let Some(fullscreen) = std::mem::take(&mut host_obj.fullscreen) {
            quick_options_fullscreen = match fullscreen {
                false => None,
                true => Some(()),
            };
        }
    };''',
    '''        } else if let Some(fullscreen) = std::mem::take(&mut host_obj.fullscreen) {
            quick_options_fullscreen = match fullscreen {
                false => None,
                true => Some(()),
            };
        }
        if quick_settings_changed {
            save_quick_settings(SavedQuickSettings {
                scale_hack: quick_options_scale_hack,
                orientation: quick_options_orientation,
                analog_stick_tilt_controls: quick_options_analog_stick_tilt_controls,
                network: quick_options_network,
                fullscreen: quick_options_fullscreen.is_some(),
            });
        }
    };'''
)

replace_once(
    '''fn setup_quick_options(
    env: &mut Environment,
    delegate: id,
    super_view: id,
    app_frame: CGRect,
) -> QuickOptionsStuff {''',
    '''fn setup_quick_options(
    env: &mut Environment,
    delegate: id,
    super_view: id,
    app_frame: CGRect,
    saved: &SavedQuickSettings,
) -> QuickOptionsStuff {'''
)
# The copyright view stays white for license readability; only settings become dark.
needle = '''    let bg_color: id = msg_class![env; UIColor whiteColor];
    () = msg![env; main_view setBackgroundColor:bg_color];'''
i = src.index('fn setup_quick_options(')
j = src.index(needle, i)
src = src[:j] + src[j:].replace(needle, '''    let bg_color: id = msg_class![env; UIColor blackColor];
    () = msg![env; main_view setBackgroundColor:bg_color];''', 1)
replace_once('RowKind::Switch("network:", false)', 'RowKind::Switch("network:", saved.network)')
replace_once('RowKind::Switch("analogStickTiltControls:", true)', 'RowKind::Switch("analogStickTiltControls:", saved.analog_stick_tilt_controls)')
replace_once('RowKind::Switch("fullscreen:", false)', 'RowKind::Switch("fullscreen:", saved.fullscreen)')
replace_once(
    '''                () = msg![env; label setTextAlignment:UITextAlignmentCenter];
                () = msg![env; main_view addSubview:label];''',
    '''                () = msg![env; label setTextAlignment:UITextAlignmentCenter];
                let white: id = msg_class![env; UIColor whiteColor];
                () = msg![env; label setTextColor:white];
                () = msg![env; main_view addSubview:label];'''
)
path.write_text(src)
print(f"Spanish GUI, black/glass theme and persisted settings patched ({len(src)} chars)")
