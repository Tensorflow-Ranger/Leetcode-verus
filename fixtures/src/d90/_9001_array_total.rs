struct Solution;

impl Solution {
    fn total(a: Vec<i32>) -> i32 {
        let mut s = 0;
        let mut i = 0;
        while i < a.len() {
            s += a[i];
            i += 1;
        }
        s
    }
}

#[test]
fn test() {
    assert_eq!(Solution::total(vec![1, 2, 3]), 6);
    assert_eq!(Solution::total(vec![-5]), -5);
}
