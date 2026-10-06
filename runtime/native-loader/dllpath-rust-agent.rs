use std::ffi::c_void;
use std::path::{Path, PathBuf};

#[link(name = "kernel32")]
extern "system" {
    fn SetDllDirectoryW(path: *const u16) -> i32;
    fn LoadLibraryExW(path: *const u16, file: *mut c_void, flags: u32) -> *mut c_void;
    fn AddDllDirectory(path: *const u16) -> *mut c_void;
    fn GetLastError() -> u32;
}

fn wide(s: &str) -> Vec<u16> {
    s.encode_utf16().chain(std::iter::once(0)).collect()
}

fn load(root: &Path, relative: &str) -> bool {
    let absolute = root.join(relative);
    let path = wide(&absolute.to_string_lossy());
    // Resolve dependencies beside the DLL, in registered COMSOL directories,
    // and in the standard Windows directories; never in the working directory.
    let handle = unsafe { LoadLibraryExW(path.as_ptr(), std::ptr::null_mut(), 0x1100) };
    if handle.is_null() {
        let code = unsafe { GetLastError() };
        eprintln!("[comsol52a-loader] failed {}: Windows error {}", absolute.display(), code);
        return false;
    }
    if std::env::var_os("COMSOL_NATIVE_TRACE").is_some() {
        eprintln!("[comsol52a-loader] loaded {}", absolute.display());
    }
    true
}

#[unsafe(no_mangle)]
pub extern "system" fn Agent_OnLoad(_vm: *mut c_void, _options: *mut u8, _reserved: *mut c_void) -> i32 {
    let root = match std::env::var_os("COMSOL_ROOT") {
        Some(value) => PathBuf::from(value),
        None => {
            eprintln!("[comsol52a-loader] COMSOL_ROOT must name the COMSOL 5.2a installation");
            return -1;
        }
    };
    if !root.is_absolute() {
        eprintln!("[comsol52a-loader] COMSOL_ROOT must be absolute");
        return -1;
    }
    for relative in ["bin\\win64", "lib\\win64", "ext\\graphicsmagick\\win64", "ext\\cadimport\\win64"] {
        let directory = root.join(relative);
        if directory.is_dir() {
            let path = wide(&directory.to_string_lossy());
            if unsafe { AddDllDirectory(path.as_ptr()) }.is_null() { return -1; }
        }
    }
    let bin = wide(&root.join("bin\\win64").to_string_lossy());
    let lib = wide(&root.join("lib\\win64").to_string_lossy());
    let gfx = wide(&root.join("ext\\graphicsmagick\\win64").to_string_lossy());
    unsafe { SetDllDirectoryW(bin.as_ptr()); }
    if !load(&root, "bin\\win64\\libiomp5md.dll") { return -1; }
    unsafe { SetDllDirectoryW(lib.as_ptr()); }
    if !load(&root, "lib\\win64\\csnutil.dll") || !load(&root, "lib\\win64\\csutil.dll") { return -1; }
    load(&root, "lib\\win64\\csdatacarrier.dll");
    load(&root, "lib\\win64\\csspecfun.dll");
    load(&root, "lib\\win64\\csblas.dll");
    load(&root, "lib\\win64\\csarray.dll");
    load(&root, "lib\\win64\\csgeom.dll");
    load(&root, "lib\\win64\\csmesh.dll");
    load(&root, "lib\\win64\\csmpi.dll");
    load(&root, "lib\\win64\\cscluster.dll");
    load(&root, "lib\\win64\\csxmesh.dll");
    load(&root, "lib\\win64\\cspost.dll");
    load(&root, "lib\\win64\\csscalapack.dll");
    load(&root, "lib\\win64\\csclusterarray.dll");
    load(&root, "lib\\win64\\csarpack.dll");
    load(&root, "lib\\win64\\cscutil.dll");
    load(&root, "lib\\win64\\csspooles.dll");
    load(&root, "lib\\win64\\cssundials.dll");
    load(&root, "lib\\win64\\cssolver.dll");
    load(&root, "lib\\win64\\cscomsolgeom.dll");
    load(&root, "lib\\win64\\csjni.dll");
    load(&root, "lib\\win64\\csavi.dll");
    load(&root, "lib\\win64\\cstextrenderer.dll");
    load(&root, "bin\\win64\\libmmd.dll");
    load(&root, "bin\\win64\\libifcoremd.dll");
    load(&root, "lib\\win64\\csgraphics_scene_common.dll");
    load(&root, "lib\\win64\\csgraphics_common.dll");
    load(&root, "bin\\win64\\cstextrenderer_wpf.dll");
    unsafe { SetDllDirectoryW(gfx.as_ptr()); }
    load(&root, "ext\\graphicsmagick\\win64\\CORE_RL_bzlib_.dll");
    load(&root, "ext\\graphicsmagick\\win64\\CORE_RL_zlib_.dll");
    load(&root, "ext\\graphicsmagick\\win64\\CORE_RL_magick_.dll");
    0
}
