struct Solution;

impl Solution {
    fn total(a: Vec<i32>) -> i32 {
        let mut s = 0;
        let mut i = 0;
        while i + 1 < a.len() {
            s += a[i];
            i += 1;
        }
        s
    }
}

