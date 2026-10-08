from pathlib import Path

path = Path("source/src/frameworks/foundation/ns_bundle.rs")
src = path.read_text(encoding="utf-8")
anchor = """ + (id)mainBundle {"""
# The actual macro has no leading space.
anchor = "+ (id)mainBundle {"
assert src.count(anchor) == 1, "Expected one NSBundle mainBundle method"

addition = """// Compatibility with older 32-bit apps that locate resource bundles by path.
+ (id)bundleWithPath:(id)path { // NSString *
    if path == nil {
        log!("DIAGNOSTICO NSBundle.bundleWithPath: ruta nula -> nil");
        return nil;
    }

    let requested = ns_string::to_rust_string(env, path).into_owned();
    let requested = requested.trim_end_matches('/');
    log!("DIAGNOSTICO NSBundle.bundleWithPath: solicitado {:?}", requested);
    if requested.is_empty() {
        log!("DIAGNOSTICO NSBundle.bundleWithPath: ruta vacia -> nil");
        return nil;
    }

    // Always share the real main bundle instance, including its lifetime rules.
    if requested == env.bundle.bundle_path().as_str().trim_end_matches('/') {
        log!("DIAGNOSTICO NSBundle.bundleWithPath: coincide con mainBundle");
        return msg_class![env; NSBundle mainBundle];
    }

    let guest_path = crate::fs::GuestPath::new(requested);
    if !env.fs.is_dir(guest_path) {
        log!("DIAGNOSTICO NSBundle.bundleWithPath: carpeta inexistente -> nil: {:?}", requested);
        return nil;
    }

    // A directory is not necessarily a bundle. Check for an Info.plist.
    let plist_path = guest_path.join("Info.plist");
    let plist_bytes = match env.fs.read(&plist_path) {
        Ok(bytes) => bytes,
        Err(_) => {
            log!("DIAGNOSTICO NSBundle.bundleWithPath: sin Info.plist -> nil: {:?}", requested);
            return nil;
        },
    };
    let info = match plist::Value::from_reader(std::io::Cursor::new(plist_bytes)) {
        Ok(plist::Value::Dictionary(info)) => info,
        _ => {
            log!("DIAGNOSTICO NSBundle.bundleWithPath: Info.plist no valido -> nil: {:?}", requested);
            return nil;
        },
    };

    let identifier = info.get("CFBundleIdentifier")
        .and_then(|value| value.as_string())
        .map(|value| value.to_owned());
    let path_object = ns_string::from_rust_string(env, requested.to_owned());
    let identifier_object = if let Some(identifier) = identifier {
        ns_string::from_rust_string(env, identifier)
    } else {
        nil
    };

    // This source version represents the main bundle in env.bundle. Nested
    // bundles can still resolve their own paths and Info.plist through these
    // fields, without mistakenly treating their path as the main bundle's.
    let bundle = NSBundleHostObject {
        bundle: None,
        bundle_path: path_object,
        bundle_identifier: identifier_object,
        bundle_url: None,
        info_dictionary: None,
    };
    let instance = env.objc.alloc_object(this, Box::new(bundle), &mut env.mem);
    log!("DIAGNOSTICO NSBundle.bundleWithPath: paquete creado {:?}, objeto {:?}", requested, instance);
    autorelease(env, instance)
}

"""
src = src.replace(anchor, addition + anchor, 1)
path.write_text(src, encoding="utf-8")
print("Added NSBundle.bundleWithPath: for 32-bit guest apps (without editing executable bytes)")
